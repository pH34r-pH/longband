#!/usr/bin/env python3
"""Validate the portable service/package contract without Fleet host secrets."""

from __future__ import annotations

import configparser
import shlex
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
unit = ROOT / "deploy/longband-alpha.service"
parser = configparser.ConfigParser(interpolation=None, strict=False)
parser.optionxform = str
if not parser.read(unit, encoding="utf-8"):
    raise SystemExit("Deployable Longband service unit is missing")
service = parser["Service"]
command = shlex.split(service.get("ExecStart", ""))
if len(command) < 5 or not command[0].endswith("/uvicorn"):
    raise SystemExit("Service must launch the packaged ASGI server via uvicorn")
if "longband_relay.app:app" not in command:
    raise SystemExit("Service must launch the packaged Longband relay application")
if "--host" not in command or command[command.index("--host") + 1:command.index("--host") + 2] != ["127.0.0.1"]:
    raise SystemExit("Longband service must bind only to loopback")
if "--forwarded-allow-ips=127.0.0.1" not in command:
    raise SystemExit("Proxy trust must be limited to local Fleet ingress")
if service.get("User") != "longband" or service.get("Group") != "longband":
    raise SystemExit("Service must use the unprivileged Longband account")
if service.get("NoNewPrivileges") != "true" or service.get("ProtectSystem") != "strict":
    raise SystemExit("Longband service sandbox was weakened")
if service.get("ReadWritePaths") != "/var/lib/longband":
    raise SystemExit("Longband write scope changed")
if service.get("WorkingDirectory") != "/opt/longband/prototype/relay":
    raise SystemExit("Longband service working directory differs from packaged source")

relay = ROOT / "prototype/relay"
with (relay / "pyproject.toml").open("rb") as input_file:
    project = tomllib.load(input_file)
if project["project"]["name"] != "longband-opaque-relay":
    raise SystemExit("Unexpected relay package identity")
assets = project["tool"]["setuptools"]["package-data"]["longband_relay"]
for pattern in ("data/*.md", "data/*.json"):
    if pattern not in assets or not list((relay / "src/longband_relay").glob(pattern)):
        raise SystemExit(f"Missing packaged discovery/privacy assets: {pattern}")
print("Longband service loopback, sandbox and package-data contract verified.")
