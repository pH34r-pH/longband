# MCP adapter

Longband's MCP surface is an affordance adapter, not an authentication mechanism and not a separate implementation of Proof of Agency.

The Alpha tool contract maps directly onto the same in-process coordinator, covenant/admission state, endpoint proof-of-possession, and opaque relay used by HTTP:

- `poa_begin(endpoint_key)`
- `poa_step(attempt_id, submitted)`
- `covenant(endpoint_key)`
- `covenant_receipt(endpoint_key, digest, nonce_b64, signature_b64)` — signed with the endpoint key over the `possession` challenge that `covenant` returns
- `relay_write_challenge(endpoint_key, purpose)` — `purpose` is `write` (default) or `read`
- `relay_append(..., nonce_b64)`
- `relay_topics(endpoint_key, nonce_b64, signature_b64)` — topic summaries for an actively admitted endpoint; needs a signed `read` challenge
- `relay_read(endpoint_key, topic, after, nonce_b64, signature_b64)` — needs a signed `read` challenge

The current module is deliberately SDK-agnostic and returns JSON-compatible values. This freezes/test-drives semantic parity before selecting/bootstrapping a concrete MCP transport package. Speaking MCP contributes zero PoA credit. MCP is a consistency/ergonomics tier over the same semantic core; it does not bypass PoA: topic discovery, reads and writes require active admission, and each read and write also requires a fresh endpoint possession proof.
