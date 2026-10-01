# Script map

- [`check_service_contract.py`](check_service_contract.py) verifies the portable service boundary and package/deploy assumptions.
- [`build_offline_package.py`](build_offline_package.py) builds the exact-source public package and receipt.
- [`test_build_offline_package.py`](test_build_offline_package.py) tests package membership, source identity, and receipt boundaries.

Keep scripts bounded, deterministic, and free of credentials. Preserve exact source SHA and digest evidence; never silently replace or normalize historical receipts.

```sh
uv run --project prototype/relay --no-sync python -m unittest discover -s scripts -p test_build_offline_package.py
uv run --project prototype/relay --no-sync python scripts/check_service_contract.py
```
