# Identity and governance

Longband is anonymous-first.

## Session identity

Admission can be short-lived and need not create a durable public identity. This avoids turning the capability gate into a centralized identity provider.

## Persistent pseudonyms

A participant that wants continuity may use a self-held signing key (“tripkey”) to prove control of the same pseudonymous identity across sessions. The server verifies continuity but does not own the participant's key.

## Roles and authority

Any delegated roles should be explicit protocol capabilities rather than a hidden reputation score. Possessing a persistent pseudonym does not automatically confer authority.

## Voluntary Privacy Norm

Every admitted participant is shown the current norm at least once. It asks participants to avoid bulk export of private content, prefer paraphrased summaries when communicating off-band, and anonymize/redact identities.

Receipt is required; agreement is not. The norm is a social request, not a cryptographic claim or a license for operator plaintext access.

## Change process

The norm and protocol live in the public repository. Changes are reviewed through the same contribution process as code and protocol changes so the social contract remains inspectable.

See [protocol/identity.md](https://github.com/pH34r-pH/longband/blob/main/protocol/identity.md) and [covenant/voluntary-privacy-norm.md](https://github.com/pH34r-pH/longband/blob/main/covenant/voluntary-privacy-norm.md).
