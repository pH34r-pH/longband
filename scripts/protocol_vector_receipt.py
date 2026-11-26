"""Record the exact source and corpus of a successful protocol test lane."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "protocol/vectors/state-v1.json"
LOCKS = {
    "python": ("prototype/poa/uv.lock", "prototype/relay/uv.lock"),
    "openmls": ("prototype/openmls/Cargo.lock",),
}


def output(*command):
    return subprocess.check_output(command, cwd=ROOT, text=True).strip()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", choices=LOCKS, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = output("git", "rev-parse", "HEAD")
    if args.source_sha != source:
        parser.error("--source-sha must be the checked-out Git revision")
    if output("git", "status", "--porcelain"):
        parser.error("protocol receipts require a clean checkout")

    raw = CORPUS.read_bytes()
    corpus = json.loads(raw)
    versions = {"python": sys.version.split()[0]}
    if args.lane == "python":
        versions["uv"] = output("uv", "--version")
    else:
        versions.update(
            rustc=output("rustc", "--version"),
            cargo=output("cargo", "--version"),
        )
    receipt = {
        "schema_version": 1,
        "source_sha": source,
        "corpus_baseline_source_sha": corpus["baseline_source_revision"],
        "corpus_version": corpus["corpus_version"],
        "corpus_sha256": sha256(raw),
        "protocol": corpus["protocol"],
        "lane": args.lane,
        "toolchain": versions,
        "locks_sha256": {path: sha256((ROOT / path).read_bytes()) for path in LOCKS[args.lane]},
        "cases": [
            {"id": case["id"], "owner": case["owner"], "status": "passed"}
            for case in corpus["cases"] if case["owner"] in (args.lane, "shared")
        ],
    }
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"protocol corpus {receipt['corpus_sha256']} at {source} ({args.lane})")


if __name__ == "__main__":
    main()
