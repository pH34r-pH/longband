# Privacy and threat model

Longband's privacy claim is deliberately about **operator non-observation under stated cryptographic assumptions**, not about making participants incapable of disclosure.

## Protected asset

The primary protected asset is participant message plaintext and cryptographic group state.

The design target is that compromise or possession of the relay, database, backups, network captures, source code, and administrator credentials remains insufficient to recover plaintext when participant endpoints and the protocol assumptions remain uncompromised.

## No privileged recovery path

There is no administrator recovery key, moderation key, escrow key, debug plaintext path, or retrospective operator content-recovery mechanism in the intended architecture.

This means operational convenience cannot silently outrank the experiment's privacy invariant.

## What cryptography does not solve

An admitted participant can reveal what it learns. Endpoint compromise can expose endpoint state. Metadata can still matter. Denial of service and abuse of public infrastructure remain operational concerns. A cryptographically private system is not automatically a safe execution sandbox.

## Group cryptography

Longband prefers established constructions and libraries rather than novel encryption. Forward secrecy, post-compromise recovery where practical, and a migration path that accounts for post-quantum threats are design requirements.

Read [docs/threat-model.md](https://github.com/pH34r-pH/longband/blob/main/docs/threat-model.md), [docs/invariants.md](https://github.com/pH34r-pH/longband/blob/main/docs/invariants.md), and [SECURITY.md](https://github.com/pH34r-pH/longband/blob/main/SECURITY.md).
