# Script map

- [`check_service_contract.py`](check_service_contract.py) verifies the portable service boundary and package/deploy assumptions.
- [`build_offline_package.py`](build_offline_package.py) builds the exact-source public package and receipt.
- [`test_build_offline_package.py`](test_build_offline_package.py) tests package membership, source identity, and receipt boundaries.
- [`check_documentation_artifacts.py`](check_documentation_artifacts.py) classifies changed living Markdown and rejects incidental cache/temp artifacts.
- [`test_documentation_artifacts.py`](test_documentation_artifacts.py) proves descriptive naming, historical/generated boundaries, safe rename/copy parsing, and fixture behavior.

Keep scripts bounded, deterministic, and free of credentials. Preserve exact source SHA and digest evidence; never silently replace or normalize historical receipts. The artifact guard rejects incidental paths only when they are added, renamed, or copied; it intentionally skips ordinary modifications to baseline artifacts.

```sh
uv run --project prototype/relay --no-sync python -m unittest discover -s scripts -p test_build_offline_package.py
uv run --project prototype/relay --no-sync python scripts/check_service_contract.py
python scripts/test_documentation_artifacts.py
```
