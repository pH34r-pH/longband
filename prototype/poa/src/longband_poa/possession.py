from __future__ import annotations

from dataclasses import dataclass
import base64
import secrets
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


@dataclass(frozen=True)
class PossessionChallenge:
    endpoint_key: str
    nonce: bytes
    issued_ns: int
    expires_ns: int

    @property
    def signing_bytes(self) -> bytes:
        return b"longband-alpha-possession-v1\x00" + self.endpoint_key.encode() + b"\x00" + self.nonce


class EndpointPossession:
    """One-use Ed25519 proof-of-possession challenge registry."""

    def __init__(self, lifetime_seconds: int = 60) -> None:
        self._lifetime_ns = lifetime_seconds * 1_000_000_000
        self._pending: dict[str, PossessionChallenge] = {}

    def begin(self, endpoint_key: str) -> PossessionChallenge:
        now = time.monotonic_ns()
        challenge = PossessionChallenge(endpoint_key, secrets.token_bytes(32), now, now + self._lifetime_ns)
        self._pending[endpoint_key] = challenge
        return challenge

    def verify(self, endpoint_key: str, public_key_b64: str, signature_b64: str) -> bool:
        challenge = self._pending.pop(endpoint_key)
        if time.monotonic_ns() >= challenge.expires_ns:
            return False
        try:
            public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64, validate=True))
            signature = base64.b64decode(signature_b64, validate=True)
            public_key.verify(signature, challenge.signing_bytes)
            derived = "ed25519:" + public_key_b64
            return secrets.compare_digest(derived, endpoint_key)
        except (ValueError, InvalidSignature):
            return False
