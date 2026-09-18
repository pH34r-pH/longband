# Ciphertext persistence

Alpha uses SQLite as the smallest durable relay store.

The persistence schema contains:

- monotonically ordered object sequence;
- topic;
- opaque payload BLOB;
- receive timestamp;
- opaque object-to-object references.

It deliberately has no participant private keys, MLS group secrets, exporter secrets, plaintext fields, recovery keys, or message interpretation.

SQLite WAL + synchronous FULL are used for the reference node. The database lives under `/var/lib/longband`, the only writable state directory granted by the reference systemd unit.

## Security boundary

SQLite durability does not make metadata private. An operator with the database can inspect topics, ordering, timestamps, sizes, references, and ciphertext. Longband's Alpha confidentiality claim is that this state is insufficient to recover protected application plaintext without participant-held MLS state.

The operator-opacity exercise in #12 must include the SQLite database, WAL/SHM files where present, filesystem snapshots/backups, and service logs.
