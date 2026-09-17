# Longband opaque relay prototype

This is the smallest server-side storage primitive for Longband M2 / issue #3.

The relay stores opaque bytes plus deliberately modeled routing metadata. It does not parse MLS application plaintext and must never receive participant group secrets, endpoint private keys, exporter secrets, or recovery keys.

Initial operations:

- `append(topic, payload, references)` -> monotonically ordered object;
- `read(topic, after)` -> opaque objects after a cursor;
- references are opaque object identifiers used for reply/thread/knowledge structures without the relay interpreting their meaning.

PoA/admission is intentionally outside this storage type. The service layer will require an endpoint-bound active admission before invoking relay writes; transport adapters must not make admission a bearer credential.

The prototype begins in memory so that protocol semantics can stabilize before persistence or Azure concerns enter the public runtime.