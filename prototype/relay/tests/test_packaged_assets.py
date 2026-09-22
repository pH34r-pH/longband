from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_installed_relay_imports_with_packaged_runtime_assets(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[3]
    relay = repo_root / "prototype" / "relay"
    poa_src = repo_root / "prototype" / "poa" / "src"
    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    python = venv / "bin" / "python"
    pip = venv / "bin" / "pip"
    subprocess.run([str(pip), "install", str(relay), str(repo_root / "prototype" / "poa")], check=True)
    code = """
import json
import sys
sys.path.insert(0, %r)
from longband_relay.http import AGENT_RESOURCE, COVENANT_RESOURCE, DISCOVERY_RESOURCE
assert "privacy" in COVENANT_RESOURCE.read_text(encoding="utf-8").lower()
assert AGENT_RESOURCE.read_text(encoding="utf-8").strip()
assert json.loads(DISCOVERY_RESOURCE.read_text(encoding="utf-8"))
print("PACKAGED_ASSETS_OK")
""" % str(poa_src)
    result = subprocess.run([str(python), "-c", code], cwd=tmp_path, text=True, capture_output=True, check=True)
    assert "PACKAGED_ASSETS_OK" in result.stdout
