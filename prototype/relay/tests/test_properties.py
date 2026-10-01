from hypothesis import given, settings, strategies as st

from longband_relay import OpaqueRelay


@settings(max_examples=40, deadline=None)
@given(
    entries=st.lists(
        st.tuples(
            st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=16),
            st.binary(min_size=1, max_size=64),
        ),
        min_size=1,
        max_size=16,
    )
)
def test_relay_round_trip_and_cursor_properties_hold_for_arbitrary_objects(entries):
    relay = OpaqueRelay()
    stored = []

    for index, (topic, payload) in enumerate(entries):
        references = (stored[-1].sequence,) if stored and index % 2 else ()
        stored.append(relay.append(topic, payload, references))

    for topic in {entry[0] for entry in entries}:
        expected = tuple(obj for obj in stored if obj.topic == topic)
        assert relay.read(topic) == expected
        for cursor in (0, *(obj.sequence for obj in expected)):
            assert relay.read(topic, after=cursor) == tuple(obj for obj in expected if obj.sequence > cursor)
