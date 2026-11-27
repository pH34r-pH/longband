from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import hmac
import secrets
import struct
import threading
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ENDPOINT_PREFIX = "ed25519:"

WRITE = "write"
READ = "read"
ADMISSION = "admission"

# Each purpose signs a different domain string, so a proof made for one operation
# can never be replayed as another.
_DOMAINS = {
    WRITE: b"longband-alpha-possession-v1\x00",
    READ: b"longband-alpha-read-v1\x00",
    ADMISSION: b"longband-alpha-admission-v1\x00",
}
_RANDOM_BYTES = 16
_ISSUED_BYTES = 8
_BODY_BYTES = _RANDOM_BYTES + _ISSUED_BYTES
NONCE_BYTES = _BODY_BYTES + hashlib.sha256().digest_size
DEFAULT_MAX_SPENT = 100_000


def endpoint_public_key(endpoint_key: str) -> str:
    """Return the base64 public key an ``ed25519:`` endpoint identifier names."""
    if not endpoint_key.startswith(ENDPOINT_PREFIX):
        raise PermissionError("endpoint identity is not an ed25519 key")
    return endpoint_key[len(ENDPOINT_PREFIX):]


@dataclass(frozen=True)
class PossessionChallenge:
    endpoint_key: str
    nonce: bytes
    issued_ns: int
    expires_ns: int
    purpose: str = WRITE
    context: bytes = b""

    @property
    def signing_bytes(self) -> bytes:
        data = _DOMAINS[self.purpose] + self.endpoint_key.encode() + b"\x00" + self.nonce
        return data + b"\x00" + self.context if self.context else data


class EndpointPossession:
    """One-use Ed25519 proof-of-possession challenges that carry no server-side state.

    A challenge nonce is ``random || issued_ns || HMAC(server_secret, purpose, endpoint,
    context, random || issued_ns)``. Issuing a challenge therefore allocates nothing and
    cannot be addressed, replaced or consumed by a third party: only a valid signature
    from the endpoint's own key spends one, and only spent nonces are remembered (until
    they would have expired). Challenges do not survive a process restart.
    """

    def __init__(self, lifetime_seconds: int = 60, max_spent: int = DEFAULT_MAX_SPENT) -> None:
        self._lifetime_ns = lifetime_seconds * 1_000_000_000
        self._max_spent = max_spent
        self._secret = secrets.token_bytes(32)
        self._spent: dict[bytes, int] = {}
        self._lock = threading.Lock()

    def _mac(self, purpose: str, endpoint_key: str, context: bytes, body: bytes) -> bytes:
        message = b"\x00".join((purpose.encode(), endpoint_key.encode(), context, body))
        return hmac.new(self._secret, message, hashlib.sha256).digest()

    def begin(self, endpoint_key: str, purpose: str = WRITE, context: bytes = b"") -> PossessionChallenge:
        if purpose not in _DOMAINS:
            raise ValueError("unknown possession purpose")
        now = time.monotonic_ns()
        body = secrets.token_bytes(_RANDOM_BYTES) + struct.pack(">Q", now)
        nonce = body + self._mac(purpose, endpoint_key, context, body)
        return PossessionChallenge(endpoint_key, nonce, now, now + self._lifetime_ns, purpose, context)

    def verify(
        self,
        endpoint_key: str,
        public_key_b64: str,
        signature_b64: str,
        nonce: bytes,
        purpose: str = WRITE,
        context: bytes = b"",
    ) -> bool:
        """Check a signed challenge; a valid proof is spent and cannot be presented again.

        Returns False for any invalid, expired or mismatched proof (nothing is consumed).
        Raises KeyError only for a *valid* proof that was already used.
        """
        if purpose not in _DOMAINS or len(nonce) != NONCE_BYTES:
            return False
        body, mac = nonce[:_BODY_BYTES], nonce[_BODY_BYTES:]
        if not hmac.compare_digest(mac, self._mac(purpose, endpoint_key, context, body)):
            return False
        (issued_ns,) = struct.unpack(">Q", body[_RANDOM_BYTES:])
        expires_ns = issued_ns + self._lifetime_ns
        now = time.monotonic_ns()
        if now < issued_ns or now >= expires_ns:
            return False
        if not hmac.compare_digest((ENDPOINT_PREFIX + public_key_b64).encode(), endpoint_key.encode()):
            return False
        challenge = PossessionChallenge(endpoint_key, nonce, issued_ns, expires_ns, purpose, context)
        try:
            public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64, validate=True))
            signature = base64.b64decode(signature_b64, validate=True)
            public_key.verify(signature, challenge.signing_bytes)
        except (ValueError, InvalidSignature):
            return False
        with self._lock:
            self._spent = {key: end for key, end in self._spent.items() if end > now}
            if mac in self._spent:
                raise KeyError("possession challenge already used")
            if len(self._spent) >= self._max_spent:
                return False
            self._spent[mac] = expires_ns
        return True
