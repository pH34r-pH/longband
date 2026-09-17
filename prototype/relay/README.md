# Longband opaque relay prototype

Smallest server-side storage primitive for Longband M2 / issue #3.

The relay stores opaque bytes plus deliberately modeled routing metadata. It does not parse MLS application plaintext and must never receive participant group secrets, endpoint private keys, exporter secrets, or recovery keys.

Initial operations are `append(topic, payload, references)` and `read(topic, after)`. References are opaque object identifiers: clients may interpret them as replies, threads, knowledge links, etc.; the relay does not.

PoA/admission remains outside this storage type. The next service layer binds writes to an admitted endpoint without turning admission into a transferable bearer credential.

The prototype begins in memory so protocol semantics can stabilize before persistence or Azure concerns enter the public runtime.