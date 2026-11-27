from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import time

from longband_poa.core import Attempt, AttemptStatus

DEFAULT_MAX_ENTRIES = 10_000


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

    This object intentionally does not mint a bearer token. Passing PoA only creates a
    *pending* admission; it never replaces an endpoint's active admission. The pending
    record becomes active when the covenant receipt is acknowledged, and callers must
    have verified endpoint key possession first (``AdmittedRelay.activate`` does this):
    knowing a public endpoint identifier, or solving PoA for it, is not enough.

    State is process-local, expires with the admission lifetime, and is capped so an
    unauthenticated caller cannot grow it without bound.
    """

    def __init__(
        self,
        covenant: Covenant,
        lifetime_seconds: int = 300,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        if lifetime_seconds <= 0:
            raise ValueError("admission lifetime must be positive")
        if max_entries <= 0:
            raise ValueError("admission capacity must be positive")
        self._covenant = covenant
        self._lifetime_ns = lifetime_seconds * 1_000_000_000
        self._max_entries = max_entries
        self._pending: dict[str, Admission] = {}
        self._admissions: dict[str, Admission] = {}

    def _prune(self, now_ns: int) -> None:
        for table in (self._pending, self._admissions):
            for key in [key for key, admission in table.items() if now_ns >= admission.expires_ns]:
                del table[key]

    def issue(self, attempt: Attempt) -> Admission:
        if attempt.status is not AttemptStatus.PASSED:
            raise ValueError("PoA attempt has not passed")
        now = time.monotonic_ns()
        self._prune(now)
        if attempt.endpoint_key not in self._pending and len(self._pending) >= self._max_entries:
            raise ValueError("admission capacity reached")
        admission = Admission(
            endpoint_key=attempt.endpoint_key,
            poa_attempt_id=attempt.attempt_id,
            issued_ns=now,
            expires_ns=now + self._lifetime_ns,
            covenant_version=self._covenant.version,
            covenant_digest=self._covenant.digest,
            covenant_received=False,
        )
        self._pending[attempt.endpoint_key] = admission
        return admission

    def covenant(self, endpoint_key: str) -> Covenant:
        if endpoint_key not in self._pending and endpoint_key not in self._admissions:
            raise KeyError("endpoint has no admission")
        return self._covenant

    def acknowledge_covenant(self, endpoint_key: str, digest: str) -> Admission:
        """Activate the pending admission. Callers must have proven key possession."""
        current = self._pending[endpoint_key]
        if digest != current.covenant_digest:
            raise ValueError("covenant digest mismatch")
        if endpoint_key not in self._admissions and len(self._admissions) >= self._max_entries:
            raise ValueError("admission capacity reached")
        updated = replace(current, covenant_received=True)
        self._admissions[endpoint_key] = updated
        del self._pending[endpoint_key]
        return updated

    def require_active(self, endpoint_key: str) -> Admission:
        admission = self._admissions.get(endpoint_key)
        if admission is None:
            if endpoint_key in self._pending:
                raise PermissionError("endpoint is not actively admitted")
            raise KeyError(endpoint_key)
        if not admission.active_for(endpoint_key):
            raise PermissionError("endpoint is not actively admitted")
        return admission
