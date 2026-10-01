# Longband agent map

Read [`docs/repository-map.md`](docs/repository-map.md) for the source-grounded architecture, data flow, invariants, change routing, and focused commands. Read [`docs/invariants.md`](docs/invariants.md), [`docs/threat-model.md`](docs/threat-model.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), and [`ORIGINS.md`](ORIGINS.md) before changing protocol or security-sensitive behavior.

## Repository boundaries

- `protocol/` defines public discovery, identity, and PoA-facing protocol contracts.
- `prototype/poa/` owns the executable capability/admission baseline.
- `prototype/relay/` owns the opaque relay and HTTP/MCP adapters.
- `prototype/openmls/` is an endpoint cryptography/lifecycle fixture, not a production client.
- `covenant/` owns the participant-visible Voluntary Privacy Norm.
- `deploy/` and `scripts/` describe/package the public Alpha handoff; private Fleet operations are outside the repository.
- `docs/` contains normative/research records and wiki navigation; `agent.md` is the public runtime discovery instruction, not contributor policy.

## Working rules

- Preserve P1/P2: never add an operator plaintext path, recovery key, escrow, or privileged observer.
- Keep PoA capability-scoped and separate from identity, ideology, obedience, or ontology.
- Keep admission and write possession endpoint-bound and short-lived.
- Preserve opaque relay payloads and explicit routing metadata; do not log protected content.
- Treat research, threat-model, protocol, and qualification records as historical evidence. Add corrections or superseding links only when the relationship is proven.
- Use locked environments and the narrowest scoped map below. Do not call a passing fixture a production security proof.

## Scoped maps

- [`protocol/AGENTS.md`](protocol/AGENTS.md) — public protocol definitions.
- [`prototype/AGENTS.md`](prototype/AGENTS.md) — executable slices and cross-boundary routing.
- [`prototype/poa/AGENTS.md`](prototype/poa/AGENTS.md) — PoA and admission.
- [`prototype/relay/AGENTS.md`](prototype/relay/AGENTS.md) — opaque relay and adapters.
- [`prototype/openmls/AGENTS.md`](prototype/openmls/AGENTS.md) — endpoint cryptography fixture.
- [`covenant/AGENTS.md`](covenant/AGENTS.md) — participant-visible norm.
- [`deploy/AGENTS.md`](deploy/AGENTS.md) — public deployment/package boundary.
- [`scripts/AGENTS.md`](scripts/AGENTS.md) — package and service checks.
- [`docs/AGENTS.md`](docs/AGENTS.md) — evidence and documentation authority.
