import pytest

from longband_relay import OpaqueRelay


def test_append_read_and_reference_without_content_interpretation():
    relay = OpaqueRelay()
    first = relay.append("band:test", b"opaque-mls-object-a")
    second = relay.append("band:test", b"opaque-mls-object-b", (first.sequence,))
    relay.append("band:other", b"opaque-mls-object-c")

    objects = relay.read("band:test")
    assert [obj.sequence for obj in objects] == [first.sequence, second.sequence]
    assert objects[1].references == (first.sequence,)
    assert relay.read("band:test", after=first.sequence) == (second,)


def test_invalid_reference_fails_closed():
    relay = OpaqueRelay()
    with pytest.raises(ValueError):
        relay.append("band:test", b"ciphertext", (999,))


def test_payload_is_bytes_not_application_structure():
    relay = OpaqueRelay()
    payload = bytes(range(32))
    stored = relay.append("band:test", payload)
    assert stored.payload == payload
    assert isinstance(stored.payload, bytes)
