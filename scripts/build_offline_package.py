#!/usr/bin/env python3
"""Build a digest-recorded, offline Alpha package on public GitHub-hosted CI.

This program handles untrusted source/dependency code only on the public runner.
It has no Fleet, Azure, deployment or private-repository credentials.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

REPOSITORY = "pH34r-pH/longband"
WORKFLOW = "Python Alpha prototypes"
SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_BUNDLE_BYTES = 350 * 1024 * 1024
MAX_WHEEL_BYTES = 100 * 1024 * 1024
MAX_SOURCE_BYTES = 300 * 1024 * 1024


class PackageError(ValueError):
    """The source checkout or built package cannot be handed to Fleet."""


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(repo: Path, environment: dict[str, str]) -> dict:
    sha = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if not SHA.fullmatch(sha) or environment.get("GITHUB_SHA", sha) != sha:
        raise PackageError("Checkout is not the exact requested 40-character source SHA")
    repository = environment.get("GITHUB_REPOSITORY", REPOSITORY)
    if repository != REPOSITORY:
        raise PackageError("The package producer repository differs from Longband")
    event = environment.get("GITHUB_EVENT_NAME", "local")
    ref = environment.get("GITHUB_REF", "local")
    if event == "push" and ref != "refs/heads/main":
        raise PackageError("Published push artifacts must originate on main")
    if environment.get("GITHUB_ACTIONS") == "true" and event not in ("push", "pull_request"):
        raise PackageError("Only public push and PR workflows may build packages")
    run_id = environment.get("GITHUB_RUN_ID", "0")
    run_attempt = environment.get("GITHUB_RUN_ATTEMPT", "0")
    if not run_id.isdecimal() or not run_attempt.isdecimal():
        raise PackageError("GitHub run ID and attempt must be decimal")
    if environment.get("GITHUB_ACTIONS") == "true" and (int(run_id) < 1 or int(run_attempt) < 1):
        raise PackageError("GitHub-run package needs its exact run ID and attempt")
    return {
        "repository": REPOSITORY, "sha": sha, "ref": ref, "event": event,
        "workflow": WORKFLOW, "workflowPath": ".github/workflows/python-alpha.yml",
        "job": "package", "runId": int(run_id),
        "runAttempt": int(run_attempt),
        "artifactName": f"longband-offline-package-{sha}-{run_id}-{run_attempt}",
    }


def record(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise PackageError(f"Package input is missing, linked or not a regular file: {path}")
    size = path.stat().st_size
    if not 0 < size <= MAX_WHEEL_BYTES:
        raise PackageError(f"Package input exceeds size limit: {path}")
    return {"filename": path.name, "sha256": digest_file(path), "sizeBytes": size}


def add_file(tar: tarfile.TarFile, name: str, path: Path) -> None:
    info = tarfile.TarInfo(name)
    info.size = path.stat().st_size
    info.mode = 0o644
    info.mtime = 0
    with path.open("rb") as source:
        tar.addfile(info, source)


def add_json(tar: tarfile.TarFile, name: str, value: dict) -> None:
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.mtime = 0
    tar.addfile(info, io.BytesIO(data))


def source_archive(repo: Path, sha: str, destination: Path) -> None:
    # Archive the checked commit's tracked files, rather than workspace files.
    raw_tar = destination.with_suffix("")
    with raw_tar.open("wb") as output:
        subprocess.run(
            ["git", "-C", str(repo), "archive", "--format=tar",
             f"--prefix=longband-{sha}/", sha], stdout=output, check=True
        )
    with raw_tar.open("rb") as source, destination.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", mtime=0, fileobj=output) as gz:
            shutil.copyfileobj(source, gz)
    raw_tar.unlink()


def extract_exact_source(archive: Path, sha: str, destination: Path) -> Path:
    """Build from archived tracked files, never from the checkout's mutable files."""
    root_name = f"longband-{sha}"
    seen: set[str] = set()
    total = 0
    with tarfile.open(archive, "r:gz") as tar:
        for item in tar:
            parts = PurePosixPath(item.name).parts
            normalized = "/".join(parts)
            if (not parts or parts[0] != root_name or ".." in parts
                    or item.name.startswith("/") or "\\" in item.name
                    or normalized in seen or not (item.isfile() or item.isdir())):
                raise PackageError("Source archive has an unsafe path, duplicate or link")
            seen.add(normalized)
            target = destination.joinpath(*parts)
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            total += item.size
            if total > MAX_SOURCE_BYTES:
                raise PackageError("Expanded source exceeds its size limit")
            target.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(item)
            if source is None:
                raise PackageError("Source archive file is unreadable")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
    root = destination / root_name
    for filename in ("prototype/poa/pyproject.toml", "prototype/relay/pyproject.toml",
                     "deploy/longband-alpha.service"):
        if not (root / filename).is_file():
            raise PackageError(f"Tracked source is missing {filename}")
    return root


def make_bundle(source: dict, archive: Path, unit: Path, wheels: Path,
                output_dir: Path) -> dict:
    files = sorted(wheels.glob("*.whl"))
    if not files or any(file.is_symlink() for file in files):
        raise PackageError("The offline wheelhouse is empty or contains linked wheels")
    unit_record = record(unit)
    wheel_records = [record(file) for file in files]
    source_record = record(archive)
    contents = [
        {"path": f"source/{archive.name}", **source_record},
        {"path": "deploy/longband-alpha.service", **unit_record},
        *({"path": f"wheelhouse/{file.name}", **entry}
          for file, entry in zip(files, wheel_records)),
    ]
    contents.sort(key=lambda entry: entry["path"])
    content_digest = hashlib.sha256(
        json.dumps(contents, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    manifest = {
        "schemaVersion": 1, "kind": "longband.offline-package",
        "state": "built-on-public-runner-no-deployment", "target": "longband-alpha",
        "source": source, "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "architecture": platform.machine(), "contentSha256": content_digest,
        "sourceArchive": source_record,
        "serviceUnit": unit_record, "wheels": wheel_records,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = output_dir / f"longband-{source['sha']}-offline.tar.gz"
    with bundle.open("xb") as output:
        with gzip.GzipFile(filename="", mode="wb", mtime=0, fileobj=output) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                add_json(tar, "manifest.json", manifest)
                add_file(tar, f"source/{archive.name}", archive)
                add_file(tar, "deploy/longband-alpha.service", unit)
                for wheel in files:
                    add_file(tar, f"wheelhouse/{wheel.name}", wheel)
    if bundle.stat().st_size > MAX_BUNDLE_BYTES:
        bundle.unlink()
        raise PackageError("Offline bundle exceeds the review size limit")
    receipt = {**manifest, "bundle": {
        "filename": bundle.name, "sha256": digest_file(bundle),
        "sizeBytes": bundle.stat().st_size,
    }}
    (output_dir / "package-receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


def build(repo: Path, output_dir: Path, environment: dict[str, str]) -> dict:
    source = identity(repo, environment)
    if sys.version_info[:2] != (3, 12) or platform.machine() != "x86_64":
        raise PackageError("Alpha service package requires Python 3.12 on x86_64")
    with tempfile.TemporaryDirectory(prefix="longband-public-package-") as temp:
        work = Path(temp)
        archive = work / f"longband-{source['sha']}-source.tar.gz"
        source_archive(repo, source["sha"], archive)
        source_root = extract_exact_source(archive, source["sha"], work / "source")
        unit = source_root / "deploy/longband-alpha.service"
        venv = work / "venv"
        wheels = work / "wheels"
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        python = str(venv / "bin/python")
        subprocess.run([
            python, "-m", "pip", "wheel", "--disable-pip-version-check", "--no-cache-dir",
            "--wheel-dir", str(wheels), str(source_root / "prototype/poa"),
            str(source_root / "prototype/relay"),
        ], check=True)
        subprocess.run([
            python, "-m", "pip", "install", "--disable-pip-version-check",
            "--no-index", "--find-links", str(wheels), "--force-reinstall",
            "longband-poa-harness==0.1.0", "longband-opaque-relay==0.1.0",
        ], check=True)
        subprocess.run([python, "-m", "pip", "check"], check=True)
        subprocess.run([
            python, "-c", "import importlib.resources as r; "
            "import longband_poa, longband_relay.app; "
            "assert r.files('longband_relay').joinpath('data/agent.md').is_file(); "
            "assert r.files('longband_relay').joinpath('data/longband.json').is_file()",
        ], check=True)
        return make_bundle(source, archive, unit, wheels, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    result = build(repository, args.output_dir, os.environ)
    print(f"Offline Longband package for {result['source']['sha']}: {result['bundle']['sha256']}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        raise SystemExit(f"Longband offline package failed: {exc}") from exc
