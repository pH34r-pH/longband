# Proof of Agency harness

Executable research harness for Longband issue #2. This is a capability experiment, not a production authentication service.

## Architecture

The core is transport-independent:

- `Coordinator` owns attempt state, fresh randomness/nonces, challenge sequencing, transcript timestamps, and scoring evidence.
- `ChallengeGenerator` creates fresh state-dependent transitions.
- `ParticipantAdapter` represents whatever is being evaluated: deterministic solver, human-mediated process, local agent, frontier agent, etc.
- HTTP/JSON and MCP are thin adapters over the same coordinator; neither transport contributes to the agency score.

## Initial challenge families

The first executable generators should favor objectively verifiable state transitions:

1. state integration;
2. contradiction detection;
3. plan/action/revision;
4. bounded tool/computation execution;
5. goal/constraint distinction.

Avoid an LLM-as-judge dependency in the baseline wherever a deterministic verifier can establish correctness.

## Transcript

Every run records:

- PoA profile/version;
- attempt ID (non-secret research identifier in offline harness only);
- challenge family and generated parameters;
- state transition sequence;
- submitted action/result;
- deterministic verifier result;
- monotonic and wall-clock timestamps;
- terminal status and failure reason.

Do not record unrelated model chain-of-thought. PoA evaluates observable transitions.

## MCP adapter

MCP should expose the same logical operations as HTTP, provisionally `poa.begin`, `poa.step`, `poa.status`, and endpoint-bound `longband.join`. The production adapter must use opaque short-lived attempt handles; speaking MCP is not evidence of agency.

## Evaluation matrix

The harness must support replayable experiments against:

- deterministic narrow solver;
- small/local model agent;
- capable local agent;
- frontier tool-using agent;
- human-only participant;
- human copy/paste mediation through a capable model;
- frontier admission followed by narrow-relay substitution;
- specialized solver with knowledge of public challenge families.

## Success criterion for this phase

Produce distributions by participant class and challenge family. Do not collapse the result into a single production threshold until the data justify one.