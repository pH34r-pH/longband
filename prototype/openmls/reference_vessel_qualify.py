#!/usr/bin/env python3
"""Run two independent OpenMLS endpoint processes through the public Longband relay."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import secrets
import subprocess
import sys
import tempfile


def read_kv(proc: subprocess.Popen[str], key: str) -> str:
    line = proc.stdout.readline()
    if not line:
        stderr = proc.stderr.read()
        raise RuntimeError(f"{key}: endpoint exited early: {stderr[-2000:]}")
    prefix = key + "="
    if not line.rstrip("\n").startswith(prefix):
        raise RuntimeError(f"{key}: unexpected endpoint response")
    return line.rstrip("\n")[len(prefix):]


def send_kv(proc: subprocess.Popen[str], key: str, value: str) -> None:
    proc.stdin.write(f"{key}={value}\n")
    proc.stdin.flush()


def endpoint(binary: pathlib.Path, mode: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [str(binary), mode],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )


def public_roundtrip(
    python: str,
    qualifier: pathlib.Path,
    base_url: str,
    topic: str,
    message_hex: str,
) -> tuple[bytes, dict]:
    with tempfile.TemporaryDirectory(prefix="longband-openmls-roundtrip-") as temp:
        root = pathlib.Path(temp)
        returned = root / "returned.mls"
        evidence = root / "qualification.json"
        subprocess.run(
            [
                python,
                str(qualifier),
                "--base-url",
                base_url,
                "--topic",
                topic,
                "--payload-hex",
                message_hex,
                "--roundtrip-output",
                str(returned),
                "--output",
                str(evidence),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        return returned.read_bytes(), json.loads(evidence.read_text())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True)
    parser.add_argument("--qualifier")
    parser.add_argument("--base-url", default="https://longband.tyharbin.com")
    parser.add_argument("--topic", default="openmls-reference-vessel")
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--plaintext-prefix", default="longband-reference-vessel:")
    parser.add_argument("--loopback", action="store_true")
    return parser.parse_args()


def validate_inputs(args: argparse.Namespace) -> tuple[pathlib.Path, pathlib.Path | None]:
    binary = pathlib.Path(args.binary).resolve()
    qualifier = pathlib.Path(args.qualifier).resolve() if args.qualifier else None
    if not binary.is_file():
        raise SystemExit("OpenMLS endpoint binary missing")
    if not args.loopback and (qualifier is None or not qualifier.is_file()):
        raise SystemExit("public qualifier missing")
    return binary, qualifier


def establish_session(alice: subprocess.Popen[str], bob: subprocess.Popen[str]) -> None:
    keypackage_hex = read_kv(bob, "keypackage_hex")
    send_kv(alice, "keypackage_hex", keypackage_hex)
    welcome_hex = read_kv(alice, "welcome_hex")
    send_kv(bob, "welcome_hex", welcome_hex)
    if read_kv(bob, "ready") != "1":
        raise RuntimeError("Bob did not become ready")


def protected_message(alice: subprocess.Popen[str], prefix_text: str) -> tuple[bytes, bytes]:
    prefix = prefix_text.encode("utf-8")
    if not prefix or len(prefix) > 128:
        raise RuntimeError("plaintext prefix must be 1..128 UTF-8 bytes")
    plaintext = prefix + secrets.token_bytes(32)
    send_kv(alice, "plaintext_hex", plaintext.hex())
    message = bytes.fromhex(read_kv(alice, "message_hex"))
    if plaintext in message:
        raise RuntimeError("serialized MLS object exposed plaintext")
    return plaintext, message


def relay_roundtrip(args: argparse.Namespace, qualifier: pathlib.Path | None, message: bytes) -> tuple[bytes, dict]:
    if args.loopback:
        return message, {
            "status": "passed",
            "base_url": "loopback",
            "topic": args.topic,
            "sequence": 0,
            "poa_families": [],
            "covenant_version": "loopback",
            "covenant_digest": "loopback",
        }
    assert qualifier is not None
    return public_roundtrip(
        sys.executable, qualifier, args.base_url, args.topic, message.hex()
    )


def validate_bob(bob: subprocess.Popen[str], returned: bytes, plaintext: bytes) -> None:
    send_kv(bob, "message_hex", returned.hex())
    recovered = bytes.fromhex(read_kv(bob, "plaintext_hex"))
    if recovered != plaintext:
        raise RuntimeError("Bob recovered different plaintext")


def finish_endpoints(alice: subprocess.Popen[str], bob: subprocess.Popen[str]) -> None:
    alice.stdin.close()
    bob.stdin.close()
    if alice.wait(timeout=5) != 0:
        raise RuntimeError("Alice endpoint exited unsuccessfully")
    if bob.wait(timeout=5) != 0:
        raise RuntimeError("Bob endpoint exited unsuccessfully")


def build_receipt(args: argparse.Namespace, plaintext: bytes, message: bytes, qualification: dict) -> dict:
    return {
        "schema_version": "longband-openmls-reference-vessel/v1",
        "status": "passed",
        "source_sha": args.source_sha,
        "fixture": "two-process-openmls/1",
        "endpoint_isolation": {
            "alice_process": "independent",
            "bob_process": "independent",
            "shared_provider_state": False,
            "state_persisted": False,
        },
        "plaintext_sha256": hashlib.sha256(plaintext).hexdigest(),
        "mls_object_sha256": hashlib.sha256(message).hexdigest(),
        "relay": {
            "base_url": qualification["base_url"],
            "topic": qualification["topic"],
            "sequence": qualification["sequence"],
            "poa_families": qualification.get("poa_families", []),
            "covenant_version": qualification.get("covenant_version"),
            "covenant_digest": qualification.get("covenant_digest"),
        },
        "bob_endpoint_validation": "OpenMLS process_message recovered exact protected plaintext",
    }


def write_receipt(path: str, receipt: dict) -> None:
    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    pathlib.Path(path).write_text(rendered + "\n")
    print(rendered)


def main() -> None:
    args = parse_args()
    binary, qualifier = validate_inputs(args)
    bob = endpoint(binary, "bob-endpoint")
    alice = endpoint(binary, "alice-endpoint")
    try:
        establish_session(alice, bob)
        plaintext, message = protected_message(alice, args.plaintext_prefix)
        returned, qualification = relay_roundtrip(args, qualifier, message)
        if returned != message:
            raise RuntimeError("relay readback changed serialized MLS object")
        validate_bob(bob, returned, plaintext)
        finish_endpoints(alice, bob)
        write_receipt(args.output, build_receipt(args, plaintext, message, qualification))
    finally:
        for proc in (alice, bob):
            if proc.poll() is None:
                proc.kill()
                proc.wait()


if __name__ == "__main__":
    main()
