from pathlib import Path

from longband_relay import OpaqueRelay


def test_relay_accepts_serialized_mls_objects_without_interpretation():
    """Cross-language contract for the Rust OpenMLS endpoint fixture.

    The OpenMLS prototype owns serialization/decryption. The relay's entire
    contract is that arbitrary serialized MLS bytes survive append/read exactly.
    A later end-to-end fixture will invoke both crates; this test freezes the
    language boundary now without reimplementing MLS in Python.
    """
    relay = OpaqueRelay()
    serialized_mls = b"\x00\x01longband-opaque-mls-fixture\xff\x10"
    stored = relay.append("mls:group-fixture", serialized_mls)
    received = relay.read("mls:group-fixture")[0]
    assert received.payload == serialized_mls
    assert received.payload is not serialized_mls  # relay made its own immutable byte value


def test_relay_source_has_no_openmls_or_plaintext_dependency():
    source = (Path(__file__).parents[1] / "src" / "longband_relay" / "core.py").read_text()
    lowered = source.lower()
    assert "openmls" not in lowered
    assert "decrypt" not in lowered
    assert "plaintext" not in lowered
