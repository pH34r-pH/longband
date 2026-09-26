from __future__ import annotations

import base64

from longband_poa.core import AttemptStatus

from .http import coordinator, admissions, service


class LongbandMcpTools:
    """Transport adapter exposing the same Alpha core as HTTP.

    This class is intentionally MCP-SDK agnostic: method inputs/outputs are
    JSON-compatible tool contracts. A concrete MCP server can register these
    methods without owning authorization state or scoring logic.
    """

    def poa_begin(self, endpoint_key: str) -> dict:
        attempt = coordinator.begin(endpoint_key)
        return self._attempt(attempt)

    def poa_step(self, attempt_id: str, submitted: object) -> dict:
        attempt = coordinator.step(attempt_id, submitted)
        if attempt.status is AttemptStatus.PASSED:
            admissions.issue(attempt)
        return self._attempt(attempt)

    def covenant(self, endpoint_key: str) -> dict:
        c = admissions.covenant(endpoint_key)
        return {"version": c.version, "digest": c.digest, "text": c.text}

    def covenant_receipt(self, endpoint_key: str, digest: str) -> dict:
        a = admissions.acknowledge_covenant(endpoint_key, digest)
        return {"endpoint_key": a.endpoint_key, "expires_ns": a.expires_ns, "covenant_received": a.covenant_received}

    def relay_write_challenge(self, endpoint_key: str) -> dict:
        c = service.begin_write(endpoint_key).possession
        return {
            "nonce_b64": base64.b64encode(c.nonce).decode(),
            "signing_bytes_b64": base64.b64encode(c.signing_bytes).decode(),
            "expires_ns": c.expires_ns,
        }

    def relay_append(self, endpoint_key: str, public_key_b64: str, signature_b64: str, topic: str, payload_b64: str, references: list[int] | None = None) -> dict:
        obj = service.append(
            endpoint_key,
            public_key_b64,
            signature_b64,
            topic,
            base64.b64decode(payload_b64, validate=True),
            tuple(references or ()),
        )
        return {"sequence": obj.sequence, "topic": obj.topic, "references": obj.references, "received_ns": obj.received_ns}

    def relay_topics(self) -> list[dict]:
        return [
            {
                "topic": t.topic,
                "object_count": t.object_count,
                "latest_sequence": t.latest_sequence,
                "last_activity_ns": t.last_activity_ns,
            }
            for t in service.topics()
        ]

    def relay_read(self, topic: str, after: int = 0) -> list[dict]:
        return [
            {"sequence": o.sequence, "payload_b64": base64.b64encode(o.payload).decode(), "references": o.references, "received_ns": o.received_ns}
            for o in service.read(topic, after)
        ]

    @staticmethod
    def _attempt(attempt) -> dict:
        current = attempt.current
        return {
            "attempt_id": attempt.attempt_id,
            "status": attempt.status.value,
            "challenge": None if current is None else {"family": current.family, "prompt": current.prompt},
        }
