import pytest
from longband_relay import OpaqueRelay

def test_append_read_reference_and_cursor():
    relay = OpaqueRelay()
    first = relay.append("band:test", b"opaque-a")
    second = relay.append("band:test", b"opaque-b", (first.sequence,))
    relay.append("band:other", b"opaque-c")
    assert relay.read("band:test") == (first, second)
    assert relay.read("band:test", after=first.sequence) == (second,)
    assert second.references == (first.sequence,)

def test_invalid_reference_fails_closed():
    with pytest.raises(ValueError):
        OpaqueRelay().append("band:test", b"ciphertext", (999,))

def test_payload_is_opaque_bytes():
    payload = bytes(range(32))
    stored = OpaqueRelay().append("band:test", payload)
    assert stored.payload == payload
    assert isinstance(stored.payload, bytes)
