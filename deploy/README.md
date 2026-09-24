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

Both public workflows now run on **every main push**. Fleet requires completed successful **push** results for jobs `poa` and `relay` in `Python Alpha prototypes` and job `test` in `OpenMLS prototype`, all on that **same SHA**; a skipped, missing, pending, canceled, failed, PR-only or mismatched run cannot qualify a deployment. The relay job also checks that the portable service still binds loopback, trusts only local proxy forwarding, uses the unprivileged account and sandbox, and packages discovery/privacy assets. Public PR checks remain focused on the touched prototype or service unit; they run on GitHub-hosted free runners with `contents: read`.

The `package` job builds and offline-installs a Python 3.12 x86_64 wheelhouse on a free public GitHub-hosted runner, in parallel with the `poa` and `relay` checks. On a main push, it publishes an Actions artifact named `longband-offline-package-<full SHA>-<run ID>-<attempt>` with a source tarball of the checked commit, the wheelhouse, the portable service unit, and a JSON receipt. The receipt records the exact source SHA, workflow run/attempt, per-wheel SHA-256 and size, and the bundle SHA-256 and size. It provides **no** Azure credentials or deployment capability. PRs test packaging but do not publish a deployable artifact.

The Python manifests constrain dependency ranges rather than locking transitive versions. The source SHA alone cannot identify the resolved wheels: Fleet must authenticate the successful `package` job on that exact main push, download its artifact using repository-scoped Actions read access, verify the complete artifact, manifest and every digest, and promote **those same bytes** with a protected identity. Fleet #177/#179 own intake, revalidation, private deployment, probes and rollback; a public Actions artifact by itself is not a deployment approval. The service unit remains portable and has no production hostname/certificate.


## Fleet qualification and operations

Private Fleet checks the `poa`, `relay`, and `package` jobs from **Python Alpha prototypes**, plus `test` from **OpenMLS prototype**, all as completed successful main-push runs for the same full source SHA. Fleet polls for candidates every six hours. Its exact-SHA manual re-request/revalidation and private archive read run on the isolated `fleet-pr-ci` lane; that archive retains package bytes but does not change the Alpha service.

The target review and any Alpha deploy, post-deploy probe, recovery, or rollback are separate protected manual operations. Resolve the reviewed source SHA before use: the legacy Fleet deploy/recovery inputs still have historical source-pin defaults. Fleet has not established a current/previous promotion pointer or retained-byte rollback proof yet; do not treat a successful source gate, archive, or target inventory as evidence that installed service bytes changed. See the [Fleet workflow and deployed-surface map](https://github.com/pH34r-pH/long-haul-fleet/blob/main/docs/workflow-and-surface-map.md), [Fleet #179](https://github.com/pH34r-pH/long-haul-fleet/issues/179), and [Fleet #321](https://github.com/pH34r-pH/long-haul-fleet/issues/321).
