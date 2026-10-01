# Mutation and property testing

Issue [#65](https://github.com/pH34r-pH/longband/issues/65) tracks mutation-guided verification for the public Python prototypes and the Rust OpenMLS fixture. This lane is deliberately bounded to Longband-owned deterministic behavior: PoA state/admission, opaque relay authorization/storage, endpoint fixture helpers, and their tests. It does not mutate third-party cryptographic internals, add protocol features, or establish a security proof.

## Python prototypes

Both Python projects expose a locked `mutation` extra containing `irradiate==0.4.3`; their locked `test` extra includes Hypothesis for property tests.

From either `prototype/poa` or `prototype/relay`:

```sh
uv sync --locked --extra test --extra mutation
uv run --no-sync python -m pytest -q
uv run --no-sync irradiate run src \
  --tests-dir tests \
  --covered-only \
  --verify-survivors \
  --report json \
  --output /tmp/longband-irradiate.json
```

For a pull-request-sized run, add `--diff origin/main` (or the exact comparison ref). The JSON report is irradiate's native Stryker/Mutation Testing Elements report-schema v2 output; it is not converted by repository code. HTML can be requested locally with `--report html` when a human-readable report is useful.

## Rust OpenMLS fixture

The fixture has a locked `proptest` development dependency. The unit properties cover arbitrary byte encoding and arbitrary application payload round trips through the endpoint-only OpenMLS fixture.

```sh
cargo test --locked
cargo install --locked --version 27.1.0 cargo-mutants
cargo mutants \
  --package longband-openmls-prototype \
  --cap-lints true \
  --exclude-re 'bob_endpoint|replace (make_fixture|make_fixture_for) ->' \
  --output /tmp/longband-cargo-mutants
```

For a pull-request-sized run from the repository root, create a binary-safe crate-relative diff and pass it with `--in-diff`:

```sh
git diff --binary origin/main HEAD -- prototype/openmls \
  | sed \
      -e 's#^diff --git a/prototype/openmls/#diff --git a/#' \
      -e 's# b/prototype/openmls/# b/#' \
      -e 's#^--- a/prototype/openmls/#--- a/#' \
      -e 's#^+++ b/prototype/openmls/#+++ b/#' \
  > /tmp/longband-openmls.diff
cd prototype/openmls
cargo mutants \
  --package longband-openmls-prototype \
  --cap-lints true \
  --exclude-re 'bob_endpoint|replace (make_fixture|make_fixture_for) ->' \
  --in-diff /tmp/longband-openmls.diff \
  --output /tmp/longband-cargo-mutants
```

The native report is `/tmp/longband-cargo-mutants/mutants.out/`, including `mutants.json` and `outcomes.json`. `cargo-mutants`' JSON format is its own native format and is intentionally retained as-is. The scoped command excludes generated whole-function replacements for the fixture constructors and interactive CLI wrapper: the former cannot compile because `MlsGroup` has no `Default`, while the latter is intentionally outside this unit-scoped run. The remaining set exercises production application-object parsing/processing and is retained as native evidence, including caught and missed mutants.

## Report boundary and interpretation

Python and Rust reports must not be merged into a made-up Longband schema or compared as if their scores had identical semantics. Irradiate emits the requested Stryker v2 schema directly; cargo-mutants emits its own native `mutants.out` evidence. A Rust-to-Stryker converter remains an explicit follow-up limit for #65 and is not introduced here because the repository does not own such an adapter.

The GitHub workflow runs the ordinary property/regression tests first, then runs diff-scoped mutation on pull requests and full mutation on manual dispatch. When a pull-request diff changes no Python source function, the workflow stores a plain no-mutants marker instead of fabricating an empty schema report. `cargo-mutants` uses exit status 2 when it finds missed mutants; the workflow accepts that expected baseline status only after verifying that the native outcomes report exists, so survivors remain review evidence rather than silently disappearing. Mutation survivors are not an automatic protocol/security verdict; no new mutation-score threshold is imposed until a baseline has been reviewed.
