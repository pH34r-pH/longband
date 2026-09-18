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
