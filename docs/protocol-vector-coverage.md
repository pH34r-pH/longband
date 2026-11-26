# Protocol vector coverage

The [version 1 corpus](../protocol/vectors/state-v1.json) binds synthetic cases to
Longband Alpha and MLS 1.0. The protocol receipt records the test checkout SHA,
corpus SHA-256, locked dependency digests, and the tool versions that ran each
case. The checked-in corpus names the baseline revision used to define its cases.

| Boundary | Executable evidence | Scope |
| --- | --- | --- |
| Python PoA and admission | Ordered steps, terminal rejection after an out-of-order answer, exact covenant receipt, and expiry | In-process Alpha coordinator and endpoint admission |
| Python relay write lifecycle | One-use write proof, deadline, missing reference, and unchanged object history on rejection | In-process relay; [#78] owns the HTTP/MCP rejection and telemetry matrix |
| SQLite relay restart | A fresh coordinator and admission service discard process-local state. A reopened SQLite store returns the identical opaque object | Clean restart in temporary storage |
| Shared opaque representation | Rust and Python return the same checked-in bytes, including zero and high-bit octets | Relay adapters preserve bytes, with cryptographic interpretation owned by OpenMLS |
| OpenMLS endpoint state | Typed wrong-group and future-epoch errors, truncated serialization, unsupported KeyPackage version, exact decode, replay, delayed messages, eviction and stale epochs | Fresh endpoint groups and the locked library defaults |
| OpenMLS pending commit | A second local commit is rejected while one is pending. Clearing the pending commit permits a peer commit, and the superseded commit is rejected | One peer-ordering fixture with two independent endpoint providers |
| HTTP relay to OpenMLS | Locked Rust commands emit and check an object in a test-specific directory. The admitted Python HTTP relay returns the exact opaque bytes | Local-process integration with synthetic endpoint keys |
| Independent endpoints | Alice and Bob run in separate processes and complete an opaque loopback relay exchange | Local integration with the existing [reference fixture](../prototype/openmls/reference_vessel_qualify.py) |

PoA cancellation, a durable coordinator or admission store, crash recovery for a
partial relay write, and automated convergence among partitions need additional
protocol design. OpenMLS fixtures exercise one cancellation and conflict path, a
default replay policy, and test membership. A deployable endpoint client and
independent operator-opacity evidence remain outside this corpus. [#12] tracks the
independent review and deployment exercises.

The [Python workflow](../.github/workflows/python-alpha.yml) runs the core vectors
without a Rust subprocess, then runs the explicit Rust-process relay check with
locked dependencies already fetched. The
[OpenMLS workflow](../.github/workflows/openmls-prototype.yml) runs the Rust
vectors offline and then runs the independent process fixture and two-phase
reload. The two vector receipts carry case IDs, versions, and fingerprints.
Endpoint state and protected message contents remain in local test storage.

The [relay authorization and metadata contract](relay-metadata.md) lists the HTTP
and MCP parity cases and records the required diagnostic fields.

[#78]: https://github.com/pH34r-pH/longband/issues/78
[#12]: https://github.com/pH34r-pH/longband/issues/12
