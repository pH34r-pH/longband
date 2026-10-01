# OpenMLS fixture map

[`src/main.rs`](src/main.rs) implements the endpoint process/fixture commands. Rust tests cover the two-party lifecycle and the opaque relay contract. [`reference_vessel_qualify.py`](reference_vessel_qualify.py) runs independent endpoint processes and emits a qualification receipt for the public CI fixture.

This is research infrastructure, not a production client. Use upstream OpenMLS APIs and the pinned toolchain/lock file. Keep group state, endpoint keys, exporter state, and plaintext at endpoints; the relay fixture may see only modeled opaque bytes and routing metadata. Do not interpret a passing test as a mathematical security proof.

```sh
cargo test --locked
```
