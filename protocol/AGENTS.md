# Protocol map

- [`discovery.md`](discovery.md) defines public service/protocol discovery.
- [`identity.md`](identity.md) defines anonymous-first endpoint identity and optional signing-key continuity.
- [`proof-of-agency.md`](proof-of-agency.md) defines the capability baseline and its claim limits.

These documents describe the public contract implemented by the prototypes. Wire or admission changes must update the matching executable tests and keep PoA distinct from cryptographic confidentiality. Do not add ideology, obedience, vendor, model, or ontology tests. Validate protocol-only edits with `git diff --check` and the focused prototype suite named in [`../docs/repository-map.md`](../docs/repository-map.md).
