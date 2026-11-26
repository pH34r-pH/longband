import base64
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from longband_poa import admission, core, possession
from longband_poa.admission import AdmissionService, Covenant
from longband_poa.core import Challenge, Coordinator
from longband_poa.possession import EndpointPossession
from longband_relay import OpaqueRelay
from longband_relay.http import app
from longband_relay.service import AdmittedRelay
from longband_relay.sqlite_store import SqliteRelay


ROOT = Path(__file__).resolve().parents[3]
CORPUS = json.loads((ROOT / "protocol/vectors/state-v1.json").read_text(encoding="utf-8"))
OPAQUE = bytes.fromhex(CORPUS["opaque_payload_hex"])
TOPIC = "fixture:protocol"
NS_PER_SECOND = 1_000_000_000


@dataclass(frozen=True)
class FixedChallenge:
    expected: int

    def generate(self) -> Challenge:
        return Challenge("fixture", {}, self.expected)


class ProtocolFixture:
    def __init__(self, monkeypatch, relay):
        self.clock = 0
        fake_time = SimpleNamespace(monotonic_ns=lambda: self.clock)
        for module in (core, admission, possession):
            monkeypatch.setattr(module, "time", fake_time)
        self.key = Ed25519PrivateKey.generate()
        self.public = base64.b64encode(
            self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode("ascii")
        self.endpoint = "ed25519:" + self.public
        self.coordinator = Coordinator([FixedChallenge(7), FixedChallenge(11)])
        self.covenant = Covenant("fixture-v1", "Public synthetic fixture")
        self.admissions = AdmissionService(self.covenant, lifetime_seconds=10)
        self.relay = relay
        self.service = AdmittedRelay(self.relay, self.admissions, EndpointPossession(lifetime_seconds=3))

    def issue(self):
        attempt = self.coordinator.begin(self.endpoint)
        for answer in (7, 11):
            self.coordinator.step(attempt.attempt_id, answer)
        return self.admissions.issue(attempt)

    def sign(self):
        challenge = self.service.begin_write(self.endpoint).possession
        return base64.b64encode(self.key.sign(challenge.signing_bytes)).decode("ascii")

    def append(self, signature, *, references=()):
        return self.service.append(self.endpoint, self.public, signature, TOPIC, OPAQUE, references)

    def admit(self):
        self.issue()
        self.admissions.acknowledge_covenant(self.endpoint, self.covenant.digest)


def ordered_poa(fixture):
    attempt = fixture.coordinator.begin(fixture.endpoint)
    states = [attempt.status.value]
    for answer in (7, 11):
        states.append(fixture.coordinator.step(attempt.attempt_id, answer).status.value)
    assert [transition.accepted for transition in attempt.transitions] == [True, True]
    return states


def out_of_order_poa(fixture):
    attempt = fixture.coordinator.begin(fixture.endpoint)
    fixture.coordinator.step(attempt.attempt_id, 11)
    result = attempt.status.value
    history = tuple(attempt.transitions)
    with pytest.raises(ValueError, match="not active"):
        fixture.coordinator.step(attempt.attempt_id, 7)
    assert tuple(attempt.transitions) == history
    return [result, "terminal", f"index:{attempt.index}"]


def receipt_lifecycle(fixture):
    current = fixture.issue()
    with pytest.raises(PermissionError, match="not actively admitted"):
        fixture.service.begin_write(fixture.endpoint)
    with pytest.raises(ValueError, match="digest mismatch"):
        fixture.admissions.acknowledge_covenant(fixture.endpoint, "sha256:" + "0" * 64)
    assert not current.covenant_received
    with pytest.raises(PermissionError):
        fixture.admissions.require_active(fixture.endpoint)
    receipt = fixture.admissions.acknowledge_covenant(fixture.endpoint, fixture.covenant.digest)
    fixture.clock = receipt.expires_ns - 1
    assert fixture.admissions.require_active(fixture.endpoint) == receipt
    fixture.clock = receipt.expires_ns
    with pytest.raises(PermissionError, match="not actively admitted"):
        fixture.service.begin_write(fixture.endpoint)
    assert not fixture.relay.read(TOPIC)
    return ["receipt-required", "digest-rejected", "active", "expired"]


def write_lifecycle(fixture):
    fixture.admit()
    signature = fixture.sign()
    stored = fixture.append(signature)
    assert stored.payload == OPAQUE
    with pytest.raises(KeyError):
        fixture.append(signature)
    assert fixture.relay.read(TOPIC) == (stored,)
    return ["appended", "proof-spent", "one-object"]


def write_expired(fixture):
    fixture.admit()
    signature = fixture.sign()
    fixture.clock = 3 * NS_PER_SECOND
    fixture.admissions.require_active(fixture.endpoint)
    with pytest.raises(PermissionError, match="proof-of-possession failed"):
        fixture.append(signature)
    assert not fixture.relay.read(TOPIC)
    return ["proof-rejected", "zero-objects"]


def write_reference(fixture):
    fixture.admit()
    signature = fixture.sign()
    with pytest.raises(ValueError, match="existing relay object"):
        fixture.append(signature, references=(812,))
    with pytest.raises(KeyError):
        fixture.append(signature)
    assert not fixture.relay.read(TOPIC)
    return ["reference-rejected", "proof-spent", "zero-objects"]


def restart(fixture, sqlite_path):
    try:
        fixture.admit()
        admitted = fixture.admissions.require_active(fixture.endpoint)
        stored = fixture.append(fixture.sign())
    finally:
        fixture.relay.close()
    with pytest.raises(KeyError):
        Coordinator([FixedChallenge(7)]).status(admitted.poa_attempt_id)
    with pytest.raises(KeyError):
        AdmissionService(fixture.covenant).require_active(fixture.endpoint)
    reloaded = SqliteRelay(sqlite_path)
    try:
        assert reloaded.read(TOPIC) == (stored,)
    finally:
        reloaded.close()
    return ["attempt-unknown", "admission-unknown", "ciphertext-retained"]


def opaque_roundtrip(fixture):
    saved = fixture.relay.append(TOPIC, OPAQUE)
    assert fixture.relay.read(TOPIC)[0].payload == saved.payload == OPAQUE
    return ["exact-bytes"]


HANDLERS = {
    "ordered-poa": ordered_poa,
    "out-of-order-poa": out_of_order_poa,
    "receipt-lifecycle": receipt_lifecycle,
    "write-lifecycle": write_lifecycle,
    "write-expired": write_expired,
    "write-reference": write_reference,
    "restart": restart,
    "opaque-roundtrip": opaque_roundtrip,
}


def test_corpus_version_and_python_case_coverage():
    assert CORPUS["corpus_version"] == 1
    assert CORPUS["protocol"]["longband"] == app.version
    cases = CORPUS["cases"]
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(case["owner"] in {"python", "openmls", "shared"} and case["start"] for case in cases)
    assert {case["id"] for case in cases if case["owner"] != "openmls"} == HANDLERS.keys()


@pytest.mark.parametrize(
    "case", [case for case in CORPUS["cases"] if case["owner"] != "openmls"],
    ids=lambda case: case["id"],
)
def test_protocol_state_vector(case, monkeypatch, tmp_path):
    if case["id"] == "restart":
        sqlite_path = tmp_path / "relay.sqlite3"
        actual = restart(ProtocolFixture(monkeypatch, SqliteRelay(sqlite_path)), sqlite_path)
    else:
        actual = HANDLERS[case["id"]](ProtocolFixture(monkeypatch, OpaqueRelay()))
    assert actual == case["expect"]
