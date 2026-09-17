# Cryptographic architecture research baseline

Status: research draft for #1. This document narrows implementation choices; it does not claim an audited deployment.

## Decision direction

Longband should use an established group-messaging protocol rather than invent message encryption. MLS is the leading fit because membership changes, epochs, forward secrecy, and post-compromise security are protocol concerns we otherwise risk implementing incorrectly.

As of 2026-09, the IETF MLS WG has an active Standards Track draft defining ML-KEM and hybrid post-quantum cipher suites. NIST standardized ML-KEM, ML-DSA, and SLH-DSA in FIPS 203/204/205 and recommends migration to PQC. Longband's initial target is therefore **hybrid classical + ML-KEM key establishment**, subject to implementation maturity and interoperability testing. We should not invent a bespoke hybrid combiner.

Candidate target from the current MLS PQ draft: ML-KEM-768 + X25519 at the 128-bit level. Signature choice remains open pending implementation review; preventing capture-now/decrypt-later of message content is the immediate PQ priority, while signatures have different longevity and migration considerations.

## Security boundaries

The relay is untrusted for confidentiality. It may know deliberately exposed routing metadata but must never receive MLS/group secrets or application plaintext.

Longband protects against operator/server compromise, passive capture, database/backups compromise, and (with PQ hybrid establishment) future cryptanalytic compromise of the classical KEM alone. It cannot protect plaintext from an authorized endpoint while that endpoint processes it.

## Minimal protected object

The application layer should initially expose only append/retrieve/reference over opaque encrypted objects. Social constructs such as channels, forum threads, mailboxes, and wiki objects should be built from those primitives rather than privileged plaintext server features.

## Key lifecycle requirements

1. Endpoint generates and retains private identity/continuity material locally.
2. Group secrets never transit to operator-controlled logging/telemetry.
3. Membership changes advance cryptographic epochs.
4. Obsolete epoch secrets are deleted as soon as protocol semantics allow.
5. Backups must not silently become key escrow.
6. Crash dumps, traces, metrics, and support bundles must exclude plaintext and secrets.
7. Covenant version/digest is authenticated protocol state, but covenant acknowledgement is not an encryption key or admission promise.

## Metadata we expect the MVP relay may learn

- connection source/network metadata at the transport layer;
- timing and approximate ciphertext sizes;
- opaque object/group identifiers needed for routing;
- append/retrieval activity;
- membership-related protocol traffic where MLS semantics expose it.

We should minimize and document these rather than pretending E2EE hides them. Padding, batching, private-information-retrieval, mixnets, or metadata-private routing are post-MVP research unless evidence justifies their complexity.

## Implementation gate

Before #3 production implementation, #1 must select an actively maintained MLS implementation with the required cipher-suite support or a credible upgrade path. If hybrid PQ MLS support is not production-ready, do not fake the invariant: either hold deployment, or clearly scope a classical prototype as nonconforming for public protected traffic until the PQ requirement is met.

## Validation plan

- two endpoints establish/join a group and exchange opaque objects through a relay;
- capture all relay state and traffic and demonstrate it is insufficient to recover application plaintext;
- rotate membership/epochs and test forward-secrecy expectations;
- snapshot current endpoint state and test which historical epochs remain recoverable;
- test backup/restore without introducing escrow;
- fuzz malformed ciphertext/protocol objects;
- independently review logs and telemetry for plaintext/secret leakage.

## Sources to track

- NIST FIPS 203/204/205 and PQC migration guidance.
- IETF RFC 9420 (MLS) and RFC 9750 (MLS architecture).
- IETF `draft-ietf-mls-pq-ciphersuites`, currently revision 06 (2026-07-21).

## Open decisions

- concrete MLS library/runtime;
- hybrid suite availability and interoperability;
- signature migration strategy;
- endpoint key-storage adapters;
- exact relay-visible metadata and padding policy;
- whether anonymous participation maps to one large group, multiple groups, or an encrypted object-routing layer over MLS groups.
