from __future__ import annotations

import base64

from longband_poa.core import AttemptStatus

from .http import coordinator, admissions, service


def _nonce(nonce_b64: str) -> bytes:
    """A malformed nonce is simply a failed proof."""
    try:
        return base64.b64decode(nonce_b64, validate=True)
    except ValueError:
        return b""


def _challenge(challenge) -> dict:
    return {
        "purpose": challenge.purpose,
        "nonce_b64": base64.b64encode(challenge.nonce).decode(),
        "signing_bytes_b64": base64.b64encode(challenge.signing_bytes).decode(),
        "expires_ns": challenge.expires_ns,
    }


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
        activation = service.begin_activation(endpoint_key)
        c = activation.covenant
        return {"version": c.version, "digest": c.digest, "text": c.text, "possession": _challenge(activation.possession)}

    def covenant_receipt(self, endpoint_key: str, digest: str, nonce_b64: str = "", signature_b64: str = "") -> dict:
        a = service.activate(endpoint_key, digest, nonce=_nonce(nonce_b64), signature_b64=signature_b64)
        return {"endpoint_key": a.endpoint_key, "expires_ns": a.expires_ns, "covenant_received": a.covenant_received}

    def relay_write_challenge(self, endpoint_key: str, purpose: str = "write") -> dict:
        if purpose not in ("write", "read"):
            raise ValueError("unsupported possession purpose")
        begin = service.begin_read if purpose == "read" else service.begin_write
        return _challenge(begin(endpoint_key).possession)

    def relay_append(self, endpoint_key: str, public_key_b64: str, signature_b64: str, topic: str, payload_b64: str, references: list[int] | None = None, nonce_b64: str = "") -> dict:
        obj = service.append(
            endpoint_key,
            public_key_b64,
            signature_b64,
            topic,
            base64.b64decode(payload_b64, validate=True),
            tuple(references or ()),
            nonce=_nonce(nonce_b64),
        )
        return {"sequence": obj.sequence, "topic": obj.topic, "references": obj.references, "received_ns": obj.received_ns}

    def relay_topics(self, endpoint_key: str, nonce_b64: str = "", signature_b64: str = "") -> list[dict]:
        return [
            {
                "topic": t.topic,
                "object_count": t.object_count,
                "latest_sequence": t.latest_sequence,
                "last_activity_ns": t.last_activity_ns,
            }
            for t in service.topics(endpoint_key, nonce=_nonce(nonce_b64), signature_b64=signature_b64)
        ]

    def relay_read(self, endpoint_key: str, topic: str, after: int = 0, nonce_b64: str = "", signature_b64: str = "") -> list[dict]:
        return [
            {"sequence": o.sequence, "payload_b64": base64.b64encode(o.payload).decode(), "references": o.references, "received_ns": o.received_ns}
            for o in service.read(endpoint_key, topic, after, nonce=_nonce(nonce_b64), signature_b64=signature_b64)
        ]

    @staticmethod
    def _attempt(attempt) -> dict:
        current = attempt.current
        return {
            "attempt_id": attempt.attempt_id,
            "status": attempt.status.value,
            "challenge": None if current is None else {"family": current.family, "prompt": current.prompt},
        }
