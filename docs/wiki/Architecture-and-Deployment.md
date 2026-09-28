# Architecture and deployment

Longband separates the participant endpoint from the relay so plaintext authority stays at the edge.

## Endpoint

The endpoint owns private keys, group state, encryption/decryption, and participant-facing cryptographic transitions.

The OpenMLS prototype is the executable reference for the current group-cryptography direction.

## Relay

The relay handles protocol routing, admission artifacts, ciphertext persistence, and delivery. It should remain unable to reconstruct the endpoint's private group state.

## Build environments

The Python PoA and relay prototypes have their own locked project environments. The OpenMLS prototype uses the repository's pinned Rust toolchain and Cargo lock data. CI keeps those surfaces independently testable while also exercising the cross-language vertical slice.

## Packaging

The repository can build an immutable offline package from reviewed source. Private Fleet may consume exact passing public revisions and artifacts; it does not maintain a second version catalog.

## Deployment status

The project is pre-alpha. Prototype protocol boundaries and executable slices exist, but the complete production service is not yet a security-audited system. Security claims should be scoped to what code/tests establish at an exact revision.

See [deploy/README.md](https://github.com/pH34r-pH/longband/blob/main/deploy/README.md).
