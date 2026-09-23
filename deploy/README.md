# Alpha service packaging

The reference deployment runs one unprivileged Longband process on loopback and places a TLS reverse proxy in front of it.

## Process boundary

- source checkout: `/opt/longband`;
- virtualenv: `/opt/longband/venv`;
- service user/group: `longband`;
- application listener: `127.0.0.1:8080` only;
- writable state root reserved at `/var/lib/longband`;
- HTTP discovery/PoA/relay and MCP are mounted in one ASGI application and therefore share one in-memory Alpha state.

The service unit uses systemd sandboxing suitable for the prototype. It deliberately does not grant access to participant endpoint keys or MLS group state.

## Reverse proxy requirements

The fleet-owned deployment must terminate TLS and proxy only to loopback. It must:

- accept public HTTPS on 443;
- set/validate Host and forwarded headers explicitly;
- restrict MCP Origin/Host values to the deployed Longband origin;
- reject unexpected Origin values before requests reach Streamable HTTP;
- avoid request/response body logging for PoA submissions and opaque relay payloads;
- not introduce a plaintext-debug mirror;
- expose only intentionally public paths.

A concrete proxy configuration belongs in private `long-haul-fleet` because deployed hostname/certificate/operations are infrastructure state.

## Persistence

Alpha currently stores relay and admission state in memory. Do not represent the current service as durable across restart. The next persistence increment should add ciphertext-only relay storage before public availability; admission/PoA state may remain ephemeral by design.

## Exact source qualification for Fleet

Private Fleet selects a full 40-character Longband commit SHA on the trusted main history. The deployable source includes `prototype/poa/**`, `prototype/relay/**` (including `src/longband_relay/data/*.md` and `*.json`), `prototype/openmls/**` for its separate prototype, and `deploy/longband-alpha.service`. The two Python package manifests and Rust lock/toolchain inputs are part of the recorded revision. Fleet pins and hashes those source inputs and records the qualified SHA, public checks and built package digest in its private release receipt; public CI does not receive a Fleet dispatch or Azure credential.

Both public workflows now run on **every main push**. Fleet requires completed successful **push** jobs `Python Alpha prototypes/poa`, `Python Alpha prototypes/relay` and `OpenMLS prototype/test` on that **same SHA**; a skipped, missing, pending, canceled, failed, PR-only or mismatched run cannot qualify a deployment. The relay job also checks that the portable service still binds loopback, trusts only local proxy forwarding, uses the unprivileged account and sandbox, and packages discovery/privacy assets. Public PR checks remain focused on the touched prototype or service unit; they run on GitHub-hosted free runners with `contents: read`.

Fleet stages/builds from that pinned source without Azure credentials, resolves dependencies in a recorded environment, then promotes the same verified package with its protected identity and probes. The Python manifests currently constrain dependency ranges rather than locking transitive versions, so a source SHA alone is not a full dependency lock. Fleet #177/#179 own automatic intake, exact source/package digests and private deployment; the service unit remains portable and has no production hostname/certificate.
