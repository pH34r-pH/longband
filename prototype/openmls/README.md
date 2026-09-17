# OpenMLS lifecycle prototype

This crate is an executable research fixture for Longband issue #1. It is not a production client and must not be deployed for protected public traffic.

## Purpose

Exercise the cryptographic lifecycle that Longband depends on while keeping the relay outside the plaintext/key boundary.

## Required scenarios

1. create Alice and Bob endpoint credentials locally;
2. Alice creates a group and publishes a KeyPackage-compatible join path;
3. Bob joins through relay-visible MLS protocol objects only;
4. Alice and Bob exchange application messages through an in-memory opaque relay;
5. capture every relay-visible byte and prove the relay fixture cannot recover the application plaintext through any supported application API;
6. advance an epoch through membership/update activity;
7. serialize permitted endpoint state, reload it, and continue the group;
8. remove a participant and establish the expected epoch transition;
9. explicitly retire obsolete endpoint state that Longband owns around OpenMLS;
10. audit test output/logging so no plaintext/group secret is emitted by the relay path.

## Implementation rule

Use public OpenMLS APIs and upstream crypto providers. Do not patch cryptographic primitives or add Longband-specific key derivation.

The prototype may use a currently supported classical RFC 9420 suite solely to exercise lifecycle behavior. Hybrid-PQ public conformance remains a separate gate from `docs/invariants.md` and ADR 0002.

## Relay model

The relay fixture is intentionally dumb. It may retain opaque protocol/application bytes plus deliberately modeled routing metadata. It has no OpenMLS provider, group state, endpoint credential private key, exporter secret, or recovery key.

Negative tests should assert architectural absence of a decrypt path rather than claim ciphertext is mathematically proven secure by unit tests.

## Version note

Dependency versions are intentionally explicit and should be refreshed against the selected current OpenMLS release before the prototype is promoted beyond research. The acceptance behavior matters more than preserving this initial dependency pin.