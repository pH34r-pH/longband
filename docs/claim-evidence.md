# Longband claims and evidence

Longband is pre-alpha. The [invariants](invariants.md) and
[threat model](threat-model.md) define the design. The table records what the
available evidence demonstrates.

## Public prototype

The Linux [Python Alpha run] and [OpenMLS run] passed at
`bac9bcc89ae4ce6d441ea6fba218a2b5620aa198`. Their vector receipts contain eight
Python cases and seven OpenMLS cases, including one shared opaque-byte case. Both
record corpus SHA-256
`e40d9f64174863b2a05aa29c7cc9fac2e12984ecfc2cb4fad359a085479fd54e`.
The historical receipts record Python 3.14.4 and the OpenMLS receipt records Rust
1.91.0. Current workflows select Python from `.python-version`, and new receipts
reject a different interpreter series.

| Property | Source and evidence | Demonstrated scope and remaining gate |
| --- | --- | --- |
| PoA and covenant receipt gate endpoint admission | [PoA coordinator](../prototype/poa/src/longband_poa/core.py), [admission](../prototype/poa/src/longband_poa/admission.py), and [protocol vectors](protocol-vector-coverage.md) | In-process ordered and rejected transitions, the exact covenant receipt and deadlines. A receipt acknowledges delivery. PoA measures behavior on the selected challenges. Calibration for other participants remains separate. |
| HTTP and MCP apply the same relay authorization decisions | [Relay service](../prototype/relay/src/longband_relay/service.py), [adapter tests](../prototype/relay/tests/test_adapter_authorization.py) and [relay metadata contract](relay-metadata.md) | Local service, HTTP and registered MCP tools share admission and expiry behavior. Appends also require a fresh, one-use endpoint signature. Reads have the admission-only assurance of the Alpha contract. |
| Relay preserves the opaque payload and exposes routing metadata | [SQLite store](../prototype/relay/src/longband_relay/sqlite_store.py), [protocol vectors](protocol-vector-coverage.md) and [diagnostics matrix](relay-metadata.md) | The local restart and HTTP bridge preserve exact bytes. Tests cover diagnostic redaction with tracing on and off. An operator can observe routing, timing and size. Ingress, collector access and retention require deployed evidence. |
| OpenMLS process fixture keeps group state at the endpoints | [OpenMLS tests](../prototype/openmls/tests/two_party.rs), [reference process fixture](../prototype/openmls/reference_vessel_qualify.py) and [OpenMLS run] | Alice and Bob run in separate local processes. The locked suite covers replay, wrong group, epoch ordering, pending commits and member eviction. Wider partition convergence, coordinator cancellation and partial-write crash recovery remain open. An authorized endpoint can disclose plaintext. |
| Voluntary Privacy Norm and Modeled Panopticon | [Norm](../covenant/voluntary-privacy-norm.md) and [research scope](research.md) | The admission fixture checks acknowledgement. Effects on participant behavior are research hypotheses. |

## Deployed Alpha and independent review

The [historical operator-opacity checkpoint] records a successful protected
exchange and negative canary scan for
`7ca104bb36fc33e6bd74dd4711d1216499c88a28`. The reported capture covered
persistence/config/source files, service journals, and readable process
metadata and memory. The operator scanner had neither participant plaintext nor
endpoint group state. The run inventoried backup resources. The capture had no
restored snapshot or controlled crash artifacts. The recorded result applies to
that revision, canary and capture set.

The protected [integrated Alpha milestone] and [operator-opacity review] remain
open. Fleet and the independent reviewer need a run-specific sanitized receipt
that binds the source and package, environment, operator access, capture
coverage, observed metadata, result and cleanup. The outstanding surfaces have
individual owners.

- [Network and TLS capture] covers ingress and operator-visible traffic.
- [Service authority inventory] classifies transport and service authority
  separately from participant group state.
- [Snapshot restore] checks an actual isolated restore and resource cleanup.
- [Controlled crash] checks crash/debug output and restoration of normal settings.

Local fixtures and the historical canary scan leave the independent security
review pending. The claims here apply to the listed evidence and the
uncompromised endpoint assumptions in the threat model.

[Python Alpha run]: https://github.com/pH34r-pH/longband/actions/runs/45779148910
[OpenMLS run]: https://github.com/pH34r-pH/longband/actions/runs/45779148893
[historical operator-opacity checkpoint]: https://github.com/pH34r-pH/longband/issues/12#issuecomment-5847797963
[integrated Alpha milestone]: https://github.com/pH34r-pH/longband/issues/11
[operator-opacity review]: https://github.com/pH34r-pH/longband/issues/12
[Network and TLS capture]: https://github.com/pH34r-pH/longband/issues/55
[Service authority inventory]: https://github.com/pH34r-pH/longband/issues/56
[Snapshot restore]: https://github.com/pH34r-pH/longband/issues/57
[Controlled crash]: https://github.com/pH34r-pH/longband/issues/58
