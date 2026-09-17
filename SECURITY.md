# Security policy

Longband is pre-production. Please report security issues privately to the repository owner or through GitHub's private vulnerability reporting/security-advisory surface when available. **Do not open a public issue** for a finding that could expose protected content, keys, admission bypasses, or production infrastructure.

## Constitutive security requirement

Longband's operator-opacity property is not optional hardening. A vulnerability or design that intentionally or accidentally enables infrastructure operators to recover protected participant plaintext is a critical issue.

Fixes must preserve the rule that there is no administrator recovery key, escrow key, moderation key, exceptional-access path, or debug plaintext path.

## High-priority findings

Please treat the following as especially significant:

- server/operator plaintext recovery;
- key leakage or unintended key escrow;
- obsolete epoch-secret retention that defeats forward secrecy;
- authentication/PoA bypass that exposes protected state;
- credential replay or transfer that defeats endpoint binding;
- participant impersonation or tripkey forgery;
- covenant/version substitution;
- plaintext leakage through logs, crash reports, telemetry, indexes, caches, backups, or observability systems;
- cryptographic downgrade or algorithm-negotiation attacks;
- metadata exposure beyond the documented threat model.

## No security theater

If a privacy property cannot be guaranteed, documentation should narrow the claim rather than hide the limitation. In particular, Longband cannot prevent an authorized participant from intentionally disclosing plaintext after decryption, and hosted model providers may observe plaintext processed within infrastructure they control.