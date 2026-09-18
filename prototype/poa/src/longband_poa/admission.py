from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time

from longband_poa.core import Attempt, AttemptStatus


@dataclass(frozen=True)
class Covenant:
    version: str
    text: str

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Admission:
    endpoint_key: str
    poa_attempt_id: str
    issued_ns: int
    expires_ns: int
    covenant_version: str
    covenant_digest: str
    covenant_received: bool

    def active_for(self, endpoint_key: str, now_ns: int | None = None) -> bool:
        now = time.monotonic_ns() if now_ns is None else now_ns
        return self.covenant_received and endpoint_key == self.endpoint_key and now < self.expires_ns


class AdmissionService:
    """Binds successful PoA and covenant receipt to one endpoint key.

    This object intentionally does not mint a bearer token. Future transports
    must prove possession of endpoint key material when invoking admitted
    operations; possession of an attempt ID alone is insufficient.
    """

    def __init__(self, covenant: Covenant, lifetime_seconds: int = 300) -> None:
        if lifetime_seconds <= 0:
            raise ValueError("admission lifetime must be positive")
        self._covenant = covenant
        self._lifetime_ns = lifetime_seconds * 1_000_000_000
        self._admissions: dict[str, Admission] = {}

    def issue(self, attempt: Attempt) -> Admission:
        if attempt.status is not AttemptStatus.PASSED:
            raise ValueError("PoA attempt has not passed")
        now = time.monotonic_ns()
        admission = Admission(
            endpoint_key=attempt.endpoint_key,
            poa_attempt_id=attempt.attempt_id,
            issued_ns=now,
            expires_ns=now + self._lifetime_ns,
            covenant_version=self._covenant.version,
            covenant_digest=self._covenant.digest,
            covenant_received=False,
        )
        self._admissions[attempt.endpoint_key] = admission
        return admission

    def covenant(self, endpoint_key: str) -> Covenant:
        if endpoint_key not in self._admissions:
            raise KeyError("endpoint has no admission")
        return self._covenant

    def acknowledge_covenant(self, endpoint_key: str, digest: str) -> Admission:
        current = self._admissions[endpoint_key]
        if digest != current.covenant_digest:
            raise ValueError("covenant digest mismatch")
        updated = Admission(**{**current.__dict__, "covenant_received": True})
        self._admissions[endpoint_key] = updated
        return updated

    def require_active(self, endpoint_key: str) -> Admission:
        admission = self._admissions[endpoint_key]
        if not admission.active_for(endpoint_key):
            raise PermissionError("endpoint is not actively admitted")
        return admission
