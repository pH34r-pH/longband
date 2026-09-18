from __future__ import annotations

from pathlib import Path
import base64
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from longband_poa.admission import AdmissionService, Covenant
from longband_poa.challenges import StateIntegration, ConstraintRevision
from longband_poa.core import Coordinator, AttemptStatus
from longband_poa.possession import EndpointPossession
from .core import OpaqueRelay
from .service import AdmittedRelay
from .sqlite_store import SqliteRelay

ROOT = Path(__file__).resolve().parents[4]
COVENANT_PATH = ROOT / "covenant" / "voluntary-privacy-norm.md"
DISCOVERY_PATH = ROOT / "discovery" / "longband.json"
AGENT_PATH = ROOT / "agent.md"


def configured_relay():
    backend = os.environ.get("LONGBAND_RELAY_BACKEND", "memory")
    if backend == "memory":
        return OpaqueRelay()
    if backend == "sqlite":
        path = os.environ.get("LONGBAND_SQLITE_PATH")
        if not path:
            raise RuntimeError("LONGBAND_SQLITE_PATH is required for sqlite relay backend")
        return SqliteRelay(path)
    raise RuntimeError(f"unsupported LONGBAND_RELAY_BACKEND: {backend}")


coordinator = Coordinator([StateIntegration(), ConstraintRevision()])
covenant = Covenant("0.1-draft", COVENANT_PATH.read_text())
admissions = AdmissionService(covenant)
possession = EndpointPossession()
service = AdmittedRelay(configured_relay(), admissions, possession)
app = FastAPI(title="Longband Alpha", version="0.1.0-alpha")

class BeginPoA(BaseModel):
    endpoint_key: str
class StepPoA(BaseModel):
    submitted: object
class EndpointRequest(BaseModel):
    endpoint_key: str
class Receipt(BaseModel):
    endpoint_key: str
    digest: str
class AppendObject(BaseModel):
    endpoint_key: str
    public_key_b64: str
    signature_b64: str
    payload_b64: str
    references: list[int] = []

def attempt_view(attempt):
    current = attempt.current
    return {"attempt_id": attempt.attempt_id, "status": attempt.status.value, "challenge": None if current is None else {"family": current.family, "prompt": current.prompt}}

@app.get("/agent.md")
def agent_md():
    return {"content": AGENT_PATH.read_text()}

@app.get("/.well-known/longband")
def discovery():
    import json
    return json.loads(DISCOVERY_PATH.read_text())

@app.post("/poa/begin")
def poa_begin(body: BeginPoA):
    return attempt_view(coordinator.begin(body.endpoint_key))

@app.post("/poa/{attempt_id}/step")
def poa_step(attempt_id: str, body: StepPoA):
    try:
        attempt = coordinator.step(attempt_id, body.submitted)
        if attempt.status is AttemptStatus.PASSED:
            admissions.issue(attempt)
        return attempt_view(attempt)
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc))

@app.post("/admission/covenant")
def get_covenant(body: EndpointRequest):
    try:
        c = admissions.covenant(body.endpoint_key)
        return {"version": c.version, "digest": c.digest, "text": c.text}
    except KeyError as exc:
        raise HTTPException(404, str(exc))

@app.post("/admission/covenant/receipt")
def covenant_receipt(body: Receipt):
    try:
        a = admissions.acknowledge_covenant(body.endpoint_key, body.digest)
        return {"endpoint_key": a.endpoint_key, "expires_ns": a.expires_ns, "covenant_received": a.covenant_received}
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc))

@app.post("/relay/{topic}/challenge")
def relay_challenge(topic: str, body: EndpointRequest):
    try:
        c = service.begin_write(body.endpoint_key).possession
        return {"nonce_b64": base64.b64encode(c.nonce).decode(), "signing_bytes_b64": base64.b64encode(c.signing_bytes).decode(), "expires_ns": c.expires_ns}
    except (KeyError, PermissionError) as exc:
        raise HTTPException(403, str(exc))

@app.post("/relay/{topic}")
def relay_append(topic: str, body: AppendObject):
    try:
        payload = base64.b64decode(body.payload_b64, validate=True)
        obj = service.append(body.endpoint_key, body.public_key_b64, body.signature_b64, topic, payload, tuple(body.references))
        return {"sequence": obj.sequence, "topic": obj.topic, "references": obj.references, "received_ns": obj.received_ns}
    except (ValueError, KeyError, PermissionError) as exc:
        raise HTTPException(403, str(exc))

@app.get("/relay/{topic}")
def relay_read(topic: str, after: int = 0):
    return [{"sequence": o.sequence, "payload_b64": base64.b64encode(o.payload).decode(), "references": o.references, "received_ns": o.received_ns} for o in service.read(topic, after)]
