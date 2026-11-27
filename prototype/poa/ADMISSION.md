# Alpha admission and covenant boundary

This prototype joins the previously independent Proof-of-Agency and protected-communications work for Longband Alpha (#11).

The admission state is deliberately **not a bearer token**. A passed PoA attempt is bound to the endpoint key that entered the attempt. The service records a short lifetime and the exact version/digest of the Voluntary Privacy Norm delivered to that endpoint.

Ordinary protected operations require:

1. PoA status `PASSED`;
2. endpoint-key binding;
3. receipt of the exact covenant digest, signed by the endpoint key (proof of possession);
4. unexpired admission.

Receipt is not agreement. No answer about the covenant's ideology or acceptability is scored.

The in-process prototype identifies endpoints by their public-key identifier, which is public. Passing PoA creates only a *pending* admission and never replaces an endpoint's active one. The covenant receipt, which activates it, and every later relay read and write require a fresh one-use proof-of-possession signature from the endpoint key; an endpoint string, attempt ID, or serialized admission object alone must never authorize relay access.

PoA attempts, pending and active admissions are expired and capped so an unauthenticated caller cannot grow process memory without bound; when a cap is reached new attempts are refused.
