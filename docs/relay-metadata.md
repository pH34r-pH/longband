# Relay authorization and metadata

The Alpha HTTP and MCP adapters call the same relay service. The public
discovery endpoints and tool list are available before admission. Passing PoA only creates a pending admission; the covenant receipt that
activates it must be signed by the endpoint key. The endpoint identifier is
public (`ed25519:` plus the public key), so it is never a credential: topic
listing, every read and every write each require an active admission and one
fresh, one-use proof from the endpoint signing key. Challenges are stateless
server-keyed values, so requesting one allocates nothing, and outstanding
challenges cannot be replaced or consumed by anyone else. The service checks
admission before verifying the proof and again afterwards.

## Authorization contract

The [adapter matrix](../prototype/relay/tests/test_adapter_authorization.py) runs
each case through the service, the HTTP route, and the MCP SDK registration with
fresh in-process state and a controlled clock. It checks the same storage decision
in all three lanes, including identical pre-existing records after a rejection.

| Operation or rejected condition | Matrix cases | Owning check |
| --- | --- | --- |
| Public discovery and tool listing | `test_public_discovery_exposes_only_the_public_entrypoints` | HTTP routes and MCP registry |
| Unknown endpoint or missing receipt | `unknown-endpoint`, `receipt-required`, `challenge-before-receipt` | Admission service |
| Active read and challenge, plus exact admission deadline | `before-admission-expiry`, `at-admission-expiry`, `after-admission-expiry`, `topics-before-admission-expiry`, `challenge-before-expiry` | Admission service |
| Reads without a fresh read proof | `topics-without-proof`, `read-without-proof` | Endpoint possession |
| Current and stale covenant receipts | `current-covenant`, `stale-covenant` | Admission service |
| Covenant receipt without a valid key-possession proof | `receipt-without-proof`, `receipt-wrong-key`, `receipt-with-read-proof` | Admitted relay |
| Valid proof and exact proof deadline | `before-proof-expiry`, `at-proof-expiry`, `after-proof-expiry` | Endpoint possession |
| Admission expires after issuance or during verification | `admission-expires-after-issue`, `admission-expires-during-proof` | Admitted relay at write |
| Endpoint or key mismatch | `endpoint-mismatch`, `key-mismatch` | Admission and endpoint possession |
| Missing or replayed challenge; independent concurrent challenges | `challenge-missing`, `challenge-replayed`, `concurrent-challenges` | One-use possession registry |
| Malformed or missing payload | `malformed-payload`, `missing-payload` | Adapter validation |

HTTP returns fixed client messages with status 403 for admission and write
denials, 400 for rejected transitions or cursors, and 422 for malformed request
fields. Unexpected route failures use a fixed 500 response and log an error
category. MCP returns a tool error with a fixed message for an invalid or failed
tool call. Rejections preserve receipts, lease deadlines, and stored objects.
Verification can consume a proof before a later admission or storage denial.

## Request and state bounds

| Bound | Value | Enforced at |
| --- | --- | --- |
| Request body | 524,288 bytes, declared or streamed (HTTP 413) | ASGI middleware |
| Endpoint identifier | 128 characters | Request model and coordinator |
| PoA submission | short scalar, 256 characters | Request model and coordinator |
| Topic name | 256 characters | Request model and relay stores |
| Opaque payload | 262,144 bytes | Relay stores |
| References per object | 64 | Request model and relay stores |
| PoA attempts | 900 s lifetime, 10,000 live | Coordinator |
| Pending and active admissions | admission lifetime, 10,000 each | Admission service |
| Spent possession proofs | proof lifetime, 100,000 live | Endpoint possession |

At a capacity limit the service refuses new work instead of evicting live state.
Per-client rate limits belong to the ingress.

## Required and retained metadata

| Surface | Fields and retention |
| --- | --- |
| SQLite relay and filesystem snapshots | Topic, sequence, references, receive timestamp, exact opaque ciphertext, and its size. These records persist across restart. The public Alpha source sets no timed deletion policy. See [persistence](../deploy/PERSISTENCE.md). |
| Participant reads and writes | Admitted callers receive routing fields and opaque payloads according to the operation. The client supplies an endpoint identifier, and the write path handles a public key and signature. PoA, admission, and possession state are process-local. |
| Requests and ingress | The service and ingress can observe timing, connection identity, paths, and request fields needed for routing. The packaged service disables raw Uvicorn access logs. The privacy contract requires ingress logging that omits paths, queries, headers and bodies containing those values. |
| Traces when enabled | Static operation and stage, result, exception class on a failure, and byte count on an append. Traces exclude topic names, request fields, exception descriptions and stack frames. Collector access and retention belong to the deployment owner. |
| Application diagnostics | Fixed client messages and coarse server failure categories. Client data, private state, and request bodies stay out of application diagnostics. |

The sentinel test checks responses, logs, traces, and SQLite for both enabled
and disabled tracing, using an in-memory exporter. Its fixtures cover a normal
write, malformed arguments, and a storage-adapter failure. An operator can still
observe stored routing and traffic metadata. [Operator-opacity qualification]
owns deployed ingress, captures, snapshots, collector settings, and independent
review.

[Operator-opacity qualification]: https://github.com/pH34r-pH/longband/issues/12
