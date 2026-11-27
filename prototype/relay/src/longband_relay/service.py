from __future__ import annotations

from dataclasses import dataclass

from longband_poa.admission import Admission, AdmissionService, Covenant
from longband_poa.possession import (
    ADMISSION,
    READ,
    WRITE,
    EndpointPossession,
    PossessionChallenge,
    endpoint_public_key,
)

from .core import OpaqueRelay, RelayObject, TopicSummary


@dataclass(frozen=True)
class WriteChallenge:
    """A one-use possession challenge issued to an actively admitted endpoint."""

    endpoint_key: str
    possession: PossessionChallenge


@dataclass(frozen=True)
class ActivationChallenge:
    covenant: Covenant
    possession: PossessionChallenge


class AdmittedRelay:
    """Authorization boundary in front of every relay read, write and admission.

    An endpoint identifier is public (it is ``"ed25519:" + public key``), so it is never
    a credential. Every admitted operation requires an active admission *and* a fresh,
    one-use signature from the endpoint's private key; PoA alone only creates a pending
    admission.
    """

    def __init__(
        self,
        relay: OpaqueRelay,
        admissions: AdmissionService,
        possession: EndpointPossession,
    ) -> None:
        self._relay = relay
        self._admissions = admissions
        self._possession = possession

    # -- admission activation -------------------------------------------------

    def begin_activation(self, endpoint_key: str) -> ActivationChallenge:
        covenant = self._admissions.covenant(endpoint_key)
        challenge = self._possession.begin(endpoint_key, ADMISSION, covenant.digest.encode())
        return ActivationChallenge(covenant, challenge)

    def activate(self, endpoint_key: str, digest: str, *, nonce: bytes, signature_b64: str) -> Admission:
        """Acknowledge the covenant, proving the caller holds the endpoint's private key."""
        covenant = self._admissions.covenant(endpoint_key)
        if digest != covenant.digest:
            raise ValueError("covenant digest mismatch")
        if not self._possession.verify(
            endpoint_key, endpoint_public_key(endpoint_key), signature_b64, nonce, ADMISSION, digest.encode()
        ):
            raise PermissionError("endpoint proof-of-possession failed")
        return self._admissions.acknowledge_covenant(endpoint_key, digest)

    # -- proofs ---------------------------------------------------------------

    def begin_write(self, endpoint_key: str) -> WriteChallenge:
        # Covenant receipt + expiry are checked before issuing a write challenge.
        self._admissions.require_active(endpoint_key)
        return WriteChallenge(endpoint_key, self._possession.begin(endpoint_key, WRITE))

    def begin_read(self, endpoint_key: str) -> WriteChallenge:
        self._admissions.require_active(endpoint_key)
        return WriteChallenge(endpoint_key, self._possession.begin(endpoint_key, READ))

    def _require_read_proof(self, endpoint_key: str, nonce: bytes, signature_b64: str) -> None:
        self._admissions.require_active(endpoint_key)
        if not self._possession.verify(
            endpoint_key, endpoint_public_key(endpoint_key), signature_b64, nonce, READ
        ):
            raise PermissionError("endpoint proof-of-possession failed")
        # An admission cannot be extended by presenting a proof close to its deadline.
        self._admissions.require_active(endpoint_key)

    # -- relay operations -----------------------------------------------------

    def append(
        self,
        endpoint_key: str,
        public_key_b64: str,
        signature_b64: str,
        topic: str,
        payload: bytes,
        references: tuple[int, ...] = (),
        *,
        nonce: bytes = b"",
    ) -> RelayObject:
        # Re-check admission at the point of mutation so an expired admission
        # cannot be extended merely by obtaining a possession challenge early.
        self._admissions.require_active(endpoint_key)
        if not self._possession.verify(endpoint_key, public_key_b64, signature_b64, nonce, WRITE):
            raise PermissionError("endpoint proof-of-possession failed")
        self._admissions.require_active(endpoint_key)
        return self._relay.append(topic, payload, references)

    def topics(self, endpoint_key: str, *, nonce: bytes = b"", signature_b64: str = "") -> tuple[TopicSummary, ...]:
        self._require_read_proof(endpoint_key, nonce, signature_b64)
        return self._relay.topics()

    def read(
        self,
        endpoint_key: str,
        topic: str,
        after: int = 0,
        *,
        nonce: bytes = b"",
        signature_b64: str = "",
    ) -> tuple[RelayObject, ...]:
        self._require_read_proof(endpoint_key, nonce, signature_b64)
        return self._relay.read(topic, after)
