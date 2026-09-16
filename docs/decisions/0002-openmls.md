# ADR 0002 — Adopt OpenMLS

Status: accepted for prototype implementation

Longband will use OpenMLS as its MLS implementation rather than continue a library bake-off.

## Rationale

- standards-oriented RFC 9420 implementation;
- active maintenance and current 0.9.x release line;
- completed independent SRLabs security audit;
- storage abstractions suitable for explicit group-state lifecycle work;
- libcrux integration provides a credible path toward the hybrid post-quantum requirement.

We accept that hybrid PQ MLS support is still evolving. We will not maintain a Longband-specific cryptographic fork merely to move faster than upstream standards/library support.

## Prototype policy

Classical OpenMLS suites may be used in local/non-production interoperability and lifecycle tests. A public deployment that claims Longband protected-content conformance remains gated on the post-quantum requirement in `docs/invariants.md` and the then-current reviewed OpenMLS/libcrux capabilities.

## Validation work

The prototype must exercise:

1. create group;
2. add/remove participant;
3. application-message exchange;
4. epoch transition;
5. persisted state reload;
6. deletion/retirement of obsolete state;
7. relay/server possession of ciphertext without participant group secrets;
8. negative tests demonstrating that relay state alone cannot decrypt application messages.

The application must not add plaintext logging, server-side search indexes, or recovery/escrow keys around OpenMLS.
