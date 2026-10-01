# Relay map

[`src/longband_relay/http.py`](src/longband_relay/http.py) and [`mcp.py`](src/longband_relay/mcp.py) expose the same coordinator/admission/service state; [`mcp_server.py`](src/longband_relay/mcp_server.py) is the MCP registration edge. [`service.py`](src/longband_relay/service.py) is the authorization boundary. [`core.py`](src/longband_relay/core.py) stores opaque in-memory objects; [`sqlite_store.py`](src/longband_relay/sqlite_store.py) is the ciphertext-only persistence option. Telemetry must remain metadata-only.

The flow is active admission → topic/read authorization or fresh possession challenge → re-check admission → signature verification → opaque append. Never add a server decryption path, operator recovery key, plaintext index, or adapter-specific authorization shortcut. Keep loopback/proxy assumptions in the deployment boundary, not in the protocol core.

```sh
uv sync --locked --extra test
uv run --no-sync python -m pytest -q
uv run --no-sync python ../../scripts/check_service_contract.py
```

For OpenMLS contract changes, also run the relay `test_openmls_contract.py` test and `cargo test --locked` from `../openmls`.
