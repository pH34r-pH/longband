import base64
import logging
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from mcp import Client
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from longband_poa.admission import Covenant
from longband_relay import OpaqueRelay, http, telemetry
from longband_relay import mcp as mcp_adapter
from longband_relay.mcp_server import mcp
from longband_relay.sqlite_store import SqliteRelay

from test_protocol_vectors import NS_PER_SECOND, OPAQUE, TOPIC, ProtocolFixture


@dataclass(frozen=True)
class Scenario:
    name: str
    method: str
    prepare: Callable[[ProtocolFixture], dict]
    status: int
    appends: int = 0


def isolate(monkeypatch, fixture):
    for module in (http, mcp_adapter):
        for name in ("coordinator", "admissions", "service"):
            monkeypatch.setattr(module, name, getattr(fixture, name))


def after_deadline(fixture, nanoseconds):
    fixture.admit()
    fixture.clock = 10 * NS_PER_SECOND + nanoseconds
    return {"endpoint_key": fixture.endpoint}


def proof_arguments(fixture, signature):
    return {
        "endpoint_key": fixture.endpoint,
        "public_key_b64": fixture.public,
        "signature_b64": signature,
        "payload_b64": base64.b64encode(OPAQUE).decode("ascii"),
        "topic": TOPIC,
    }


def with_proof(fixture, mode):
    fixture.admit()
    if mode == "missing":
        return proof_arguments(fixture, "")
    if mode == "admission-expires":
        fixture.clock = 9 * NS_PER_SECOND
    signature = fixture.sign()
    arguments = proof_arguments(fixture, signature)
    if mode == "replaced":
        fixture.sign()
    elif mode == "replayed":
        fixture.append(signature)
    elif mode == "wrong-key":
        arguments["public_key_b64"] = base64.b64encode(bytes(32)).decode("ascii")
    elif mode == "wrong-endpoint":
        arguments["endpoint_key"] = "unadmitted-fixture"
    elif mode == "bad-payload":
        arguments["payload_b64"] = "invalid fixture base64"
    elif mode == "missing-payload":
        del arguments["payload_b64"]
    elif mode == "admission-expires":
        fixture.clock = 10 * NS_PER_SECOND
    elif isinstance(mode, int):
        fixture.clock = 3 * NS_PER_SECOND + mode
    return arguments


def expire_during_proof(fixture):
    arguments = with_proof(fixture, "fresh")
    possession = fixture.service._possession
    verify = possession.verify

    def finish_proof(*args):
        verified = verify(*args)
        fixture.clock = 10 * NS_PER_SECOND
        return verified

    possession.verify = finish_proof
    return arguments


def pending_receipt(fixture):
    fixture.issue()
    return {"endpoint_key": fixture.endpoint}


def covenant_receipt(fixture, *, current):
    fixture.issue()
    digest = fixture.covenant.digest if current else Covenant("previous-fixture", "previous text").digest
    return {"endpoint_key": fixture.endpoint, "digest": digest}


READ_CASES = [
    Scenario("unknown-endpoint", "relay_topics", lambda _f: {"endpoint_key": "unadmitted-fixture"}, 403),
    Scenario("receipt-required", "relay_topics", pending_receipt, 403),
    Scenario("before-admission-expiry", "relay_read", lambda f: after_deadline(f, -1), 200),
    Scenario("at-admission-expiry", "relay_read", lambda f: after_deadline(f, 0), 403),
    Scenario("after-admission-expiry", "relay_read", lambda f: after_deadline(f, 1), 403),
    Scenario("stale-covenant", "covenant_receipt", lambda f: covenant_receipt(f, current=False), 400),
    Scenario("current-covenant", "covenant_receipt", lambda f: covenant_receipt(f, current=True), 200),
    Scenario("challenge-before-receipt", "relay_write_challenge", pending_receipt, 403),
    Scenario("challenge-before-expiry", "relay_write_challenge", lambda f: after_deadline(f, -1), 200),
]
WRITE_CASES = [
    Scenario(name, "relay_append", lambda fixture, mode=mode: with_proof(fixture, mode), status, appends)
    for name, mode, status, appends in [
        ("before-proof-expiry", -1, 200, 1),
        ("at-proof-expiry", 0, 403, 0),
        ("after-proof-expiry", 1, 403, 0),
        ("admission-expires-after-issue", "admission-expires", 403, 0),
        ("endpoint-mismatch", "wrong-endpoint", 403, 0),
        ("key-mismatch", "wrong-key", 403, 0),
        ("challenge-missing", "missing", 403, 0),
        ("challenge-replaced", "replaced", 403, 0),
        ("challenge-replayed", "replayed", 403, 0),
        ("malformed-payload", "bad-payload", 403, 0),
        ("missing-payload", "missing-payload", 422, 0),
    ]
] + [Scenario("admission-expires-during-proof", "relay_append", expire_during_proof, 403)]


HTTP_ROUTES = {
    "relay_topics": ("GET", "/topics"),
    "relay_read": ("GET", f"/relay/{TOPIC}"),
    "relay_write_challenge": ("POST", f"/relay/{TOPIC}/challenge"),
    "covenant_receipt": ("POST", "/admission/covenant/receipt"),
    "relay_append": ("POST", f"/relay/{TOPIC}"),
}
HTTP_ERRORS = {
    400: "Covenant receipt rejected",
    422: "Invalid request",
}


def invoke_http(client, method, arguments):
    verb, path = HTTP_ROUTES[method]
    if verb == "GET":
        return client.get(path, params=arguments)
    body = {name: value for name, value in arguments.items() if name != "topic"}
    return client.post(path, json=body)


def invoke_core(fixture, method, arguments):
    endpoint = arguments["endpoint_key"]
    actions = {
        "relay_topics": lambda: fixture.service.topics(endpoint),
        "relay_read": lambda: fixture.service.read(endpoint, TOPIC),
        "relay_write_challenge": lambda: fixture.service.begin_write(endpoint),
        "covenant_receipt": lambda: fixture.admissions.acknowledge_covenant(endpoint, arguments["digest"]),
        "relay_append": lambda: fixture.service.append(
            endpoint, arguments["public_key_b64"], arguments["signature_b64"], TOPIC,
            base64.b64decode(arguments["payload_b64"], validate=True),
        ),
    }
    try:
        actions[method]()
    except (KeyError, PermissionError, ValueError):
        return False
    return True


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter", ["core", "http", "mcp"])
@pytest.mark.parametrize("scenario", READ_CASES + WRITE_CASES, ids=lambda scenario: scenario.name)
async def test_authorization_has_the_same_storage_decision(monkeypatch, adapter, scenario):
    fixture = ProtocolFixture(monkeypatch, OpaqueRelay())
    isolate(monkeypatch, fixture)
    arguments = scenario.prepare(fixture)
    before = fixture.relay.read(TOPIC)
    accepted = scenario.status == 200
    if adapter == "core":
        assert invoke_core(fixture, scenario.method, arguments) is accepted
    elif adapter == "http":
        with TestClient(http.app) as client:
            response = invoke_http(client, scenario.method, arguments)
        assert response.status_code == scenario.status
        if not accepted:
            detail = "Relay write rejected" if scenario.method == "relay_append" else "Active admission required"
            assert response.json() == {"detail": HTTP_ERRORS.get(scenario.status, detail)}
    else:
        if scenario.method == "relay_read":
            arguments["topic"] = TOPIC
        async with Client(mcp) as client:
            result = await client.call_tool(scenario.method, arguments)
        assert bool(result.is_error) == (not accepted)
        if not accepted:
            assert result.content[0].text == "Longband tool call rejected"

    after = fixture.relay.read(TOPIC)
    assert len(after) == len(before) + scenario.appends
    assert after[:len(before)] == before
    if scenario.appends:
        assert after[-1].payload == OPAQUE


@pytest.mark.asyncio
async def test_public_discovery_exposes_only_the_public_entrypoints(monkeypatch):
    fixture = ProtocolFixture(monkeypatch, OpaqueRelay())
    isolate(monkeypatch, fixture)
    with TestClient(http.app) as client:
        public = [client.get(path) for path in ("/", "/llms.txt", "/agent.md", "/.well-known/longband")]
    assert all(result.status_code == 200 for result in public)
    async with Client(mcp) as client:
        assert any(tool.name == "poa_begin" for tool in (await client.list_tools()).tools)
    assert not fixture.relay.read(TOPIC)


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False], ids=["traced", "untraced"])
async def test_diagnostics_and_sqlite_exclude_protected_values(monkeypatch, tmp_path, caplog, request, enabled):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    request.addfinalizer(provider.shutdown)
    monkeypatch.setattr(telemetry, "_enabled", enabled)
    monkeypatch.setattr(telemetry, "tracer", provider.get_tracer("synthetic-fixture"))
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.WARNING, logger="httpx")  # The fixture client's own access log is outside the app.
    path = tmp_path / "opaque.sqlite3"
    private_values = [
        "synthetic-protected-plaintext",
        "synthetic-endpoint-private-key",
        "synthetic-group-secret",
        "synthetic-bearer-credential",
        "synthetic-sensitive-query",
        "synthetic-unknown-tool-name",
    ]
    with closing(SqliteRelay(path)) as relay:
        fixture = ProtocolFixture(monkeypatch, relay)
        isolate(monkeypatch, fixture)
        fixture.admit()
        arguments = proof_arguments(fixture, fixture.sign())
        headers = {
            "Authorization": f"Bearer {private_values[3]}",
            "X-Fixture-Endpoint-Key": private_values[1],
        }
        with TestClient(http.app) as http_client:
            write = http_client.post(f"/relay/{TOPIC}", json={
                name: value for name, value in arguments.items() if name != "topic"
            }, headers=headers)
            assert write.status_code == 200
            malformed = http_client.get(
                f"/relay/{TOPIC}", params={"endpoint_key": private_values[0], "after": private_values[4]},
            )
            assert malformed.json() == {"detail": "Invalid request"}

            def broken_read(*_args, **_kwargs):
                raise RuntimeError(private_values[2])

            monkeypatch.setattr(fixture.service, "read", broken_read)
            failed = http_client.get(f"/relay/{TOPIC}", params={"endpoint_key": fixture.endpoint})
            assert failed.json() == {"detail": "Longband operation failed"}
        async with Client(mcp) as client:
            for name, values in [
                ("relay_read", {"endpoint_key": fixture.endpoint, "topic": TOPIC}),
                ("relay_read", {"endpoint_key": [private_values[1]], "topic": TOPIC}),
                (private_values[5], {}),
            ]:
                result = await client.call_tool(name, values)
                assert result.is_error and result.content[0].text == "Longband tool call rejected"
        assert relay.read(TOPIC)[0].payload == OPAQUE

    with closing(sqlite3.connect(path)) as database:
        dump = "\n".join(database.iterdump())
    spans = exporter.get_finished_spans()
    assert bool(spans) is enabled
    if enabled:
        assert {span.attributes["longband.result"] for span in spans} == {"ok", "error"}
        assert all(not span.events for span in spans)
        assert any(span.attributes.get("longband.payload_bytes") == len(OPAQUE) for span in spans)
        assert all("longband.topic" not in span.attributes for span in spans)
    searched = dump + caplog.text + write.text + malformed.text + failed.text + "\n".join(
        span.to_json() for span in spans
    )
    assert TOPIC in dump
    for value in [*private_values, fixture.endpoint, arguments["signature_b64"]]:
        assert value not in searched
