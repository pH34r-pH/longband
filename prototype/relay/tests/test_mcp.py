import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from longband_relay.mcp import LongbandMcpTools


def solve(challenge):
    p = challenge["prompt"]
    if challenge["family"] == "state-integration":
        return (p["left"] + p["right"]) * p["salt"]
    if challenge["family"] == "constraint-revision":
        return p["original_limit"] + p["revision"]
    raise AssertionError(challenge["family"])


def test_mcp_tool_contract_reaches_same_admitted_relay_boundary():
    tools = LongbandMcpTools()
    private = Ed25519PrivateKey.generate()
    raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public = base64.b64encode(raw).decode()
    endpoint = "ed25519:" + public

    state = tools.poa_begin(endpoint)
    while state["status"] == "active":
        state = tools.poa_step(state["attempt_id"], solve(state["challenge"]))
    assert state["status"] == "passed"

    covenant = tools.covenant(endpoint)
    tools.covenant_receipt(endpoint, covenant["digest"])
    challenge = tools.relay_write_challenge(endpoint)
    signature = base64.b64encode(private.sign(base64.b64decode(challenge["signing_bytes_b64"]))).decode()

    payload = base64.b64encode(b"opaque-mcp-object").decode()
    tools.relay_append(endpoint, public, signature, "mcp:test", payload)
    assert tools.relay_read(endpoint, "mcp:test")[0]["payload_b64"] == payload
    topics = tools.relay_topics(endpoint)
    assert any(t["topic"] == "mcp:test" and t["object_count"] >= 1 for t in topics)

def test_mcp_topics_and_reads_require_admission():
    tools = LongbandMcpTools()
    import pytest
    with pytest.raises((KeyError, PermissionError)):
        tools.relay_topics("ed25519:unknown")
    with pytest.raises((KeyError, PermissionError)):
        tools.relay_read("ed25519:unknown", "mcp:test")
