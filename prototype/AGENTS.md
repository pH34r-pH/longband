# Prototype map

The prototypes are deliberately separate experiments with a narrow contract between them:

- [`poa/`](poa/) evaluates endpoint-bound capability and issues short-lived admission state.
- [`relay/`](relay/) consumes admission, requires fresh write possession, and stores opaque objects; HTTP and MCP are adapters over one core.
- [`openmls/`](openmls/) exercises endpoint-only group cryptography and lifecycle through an opaque relay fixture.

Keep cross-prototype behavior explicit. A PoA test does not prove cryptographic confidentiality, and an OpenMLS fixture does not qualify the deployed Alpha service. Run the scoped `AGENTS.md` command in the changed prototype, then the relay/OpenMLS boundary checks.
