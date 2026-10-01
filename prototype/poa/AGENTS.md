# Proof-of-Agency map

[`src/longband_poa/core.py`](src/longband_poa/core.py) owns the attempt state machine and challenge sequencing. [`challenges.py`](src/longband_poa/challenges.py), [`trajectory.py`](src/longband_poa/trajectory.py), and [`calibration.py`](src/longband_poa/calibration.py) define state-dependent capability checks. [`possession.py`](src/longband_poa/possession.py) handles endpoint proof-of-possession. [`admission.py`](src/longband_poa/admission.py) binds a passed attempt to covenant receipt and expiry.

Preserve the agency-floor, capability-not-obedience, endpoint binding, one-use/fresh challenge, and short-lived admission invariants. Do not claim PoA proves consciousness, human exclusion, model identity, or general security.

```sh
uv sync --locked --extra test
uv run --no-sync python -m pytest -q
```
