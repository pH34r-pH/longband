from __future__ import annotations

from dataclasses import dataclass
import base64

from longband_poa.admission import AdmissionService
from longband_poa.possession import EndpointPossession, PossessionChallenge

from .core import OpaqueRelay, RelayObject


@dataclass(frozen=True)
class WriteChallenge:
    endpoint_key: str
    possession: PossessionChallenge


class AdmittedRelay:
    """Authorization boundary immediately in front of opaque relay writes."""

    def __init__(
        self,
        relay: OpaqueRelay,
        admissions: AdmissionService,
        possession: EndpointPossession,
    ) -> None:
        self._relay = relay
        self._admissions = admissions
        self._possession = possession

    def begin_write(self, endpoint_key: str) -> WriteChallenge:
        # Covenant receipt + expiry are checked before issuing a write challenge.
        self._admissions.require_active(endpoint_key)
        return WriteChallenge(endpoint_key, self._possession.begin(endpoint_key))

    def append(
        self,
        endpoint_key: str,
        public_key_b64: str,
        signature_b64: str,
        topic: str,
        payload: bytes,
        references: tuple[int, ...] = (),
    ) -> RelayObject:
        # Re-check admission at the point of mutation so an expired admission
        # cannot be extended merely by obtaining a possession challenge early.
        self._admissions.require_active(endpoint_key)
        if not self._possession.verify(endpoint_key, public_key_b64, signature_b64):
            raise PermissionError("endpoint proof-of-possession failed")
        return self._relay.append(topic, payload, references)

    def read(self, topic: str, after: int = 0) -> tuple[RelayObject, ...]:
        # Alpha keeps ciphertext reads public to avoid creating a bearer-token
        # read path. Protected plaintext remains available only to MLS endpoints.
        return self._relay.read(topic, after)
