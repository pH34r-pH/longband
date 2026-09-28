# Development and qualification

Longband spans Python and Rust because the relay/PoA and endpoint cryptography have different implementation boundaries.

## Python prototypes

From each Python prototype directory, use its locked environment and run the local test suite. The repository README carries the current exact commands.

## OpenMLS prototype

The Rust endpoint builds against the pinned toolchain and lock file. Run `cargo test --locked` and the fixture qualification path encoded in CI.

## Cross-language checks

The relay/OpenMLS vertical slice is a contract boundary. Changes should prove both sides still agree on the wire/fixture behavior rather than relying on independent unit tests alone.

## Security-sensitive changes

Cryptographic, identity, PoA, persistence, and privacy-norm changes deserve explicit threat-model review. Avoid inventing custom cryptographic constructions to simplify implementation.

## Contribution model

Humans and agents can contribute. A pull request should identify the protocol invariant or research boundary it affects, include reproducible validation, and keep claims no stronger than the evidence.

See [CONTRIBUTING.md](https://github.com/pH34r-pH/longband/blob/main/CONTRIBUTING.md).
