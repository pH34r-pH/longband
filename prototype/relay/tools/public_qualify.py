#!/usr/bin/env python3
"""Qualify the public Longband Alpha PoA -> admission -> relay vertical slice."""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import urllib.error
import urllib.request

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def request(base: str, method: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "User-Agent": "longband-alpha-qualifier/0.1"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def solve(challenge):
    p = challenge["prompt"]
    if challenge["family"] == "state-integration":
        return (p["left"] + p["right"]) * p["salt"]
    if challenge["family"] == "constraint-revision":
        return p["original_limit"] + p["revision"]
    raise RuntimeError(f"unsupported PoA family: {challenge['family']}")


def qualify(base: str, topic: str, payload: bytes | None = None, roundtrip_output: str | None = None):
    discovery = request(base, "GET", "/.well-known/longband")
    if discovery.get("name") != "Longband":
        raise RuntimeError("unexpected discovery document")

    private = Ed25519PrivateKey.generate()
    raw_public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public_b64 = base64.b64encode(raw_public).decode()
    endpoint_key = "ed25519:" + public_b64

    state = request(base, "POST", "/poa/begin", {"endpoint_key": endpoint_key})
    families = []
    while state["status"] == "active":
        families.append(state["challenge"]["family"])
        state = request(
            base,
            "POST",
            f"/poa/{state['attempt_id']}/step",
            {"submitted": solve(state["challenge"])},
        )
    if state["status"] != "passed":
        raise RuntimeError(f"PoA ended as {state['status']}")

    covenant = request(base, "POST", "/admission/covenant", {"endpoint_key": endpoint_key})
    receipt = request(
        base,
        "POST",
        "/admission/covenant/receipt",
        {"endpoint_key": endpoint_key, "digest": covenant["digest"]},
    )
    if not receipt.get("covenant_received"):
        raise RuntimeError("covenant receipt was not accepted")

    possession = request(base, "POST", f"/relay/{topic}/challenge", {"endpoint_key": endpoint_key})
    signing_bytes = base64.b64decode(possession["signing_bytes_b64"], validate=True)
    signature_b64 = base64.b64encode(private.sign(signing_bytes)).decode()

    marker = payload if payload is not None else ("longband-public-qualification:" + secrets.token_hex(16)).encode()
    write = request(
        base,
        "POST",
        f"/relay/{topic}",
        {
            "endpoint_key": endpoint_key,
            "public_key_b64": public_b64,
            "signature_b64": signature_b64,
            "payload_b64": base64.b64encode(marker).decode(),
            "references": [],
        },
    )
    objects = request(base, "GET", f"/relay/{topic}?after={max(0, int(write['sequence']) - 1)}")
    returned = next((base64.b64decode(obj["payload_b64"], validate=True) for obj in objects if base64.b64decode(obj["payload_b64"], validate=True) == marker), None)
    if returned is None:
        raise RuntimeError("written opaque object was not returned by relay readback")
    if roundtrip_output:
        with open(roundtrip_output, "wb") as handle:
            handle.write(returned)

    return {
        "status": "passed",
        "base_url": base,
        "poa_families": families,
        "covenant_version": covenant["version"],
        "covenant_digest": covenant["digest"],
        "topic": topic,
        "sequence": write["sequence"],
        "endpoint_key_sha256_only": __import__("hashlib").sha256(endpoint_key.encode()).hexdigest(),
        "payload": ("caller-supplied opaque bytes (value intentionally omitted)" if payload is not None else "opaque qualification marker (value intentionally omitted)"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://longband.tyharbin.com")
    parser.add_argument("--topic", default="qualification")
    parser.add_argument("--output")
    parser.add_argument("--payload-hex", help="Caller-owned opaque bytes to round-trip; value is never emitted in evidence")
    parser.add_argument("--roundtrip-output", help="Write the exact relay-returned bytes locally; never included in evidence")
    args = parser.parse_args()
    payload = bytes.fromhex(args.payload_hex) if args.payload_hex else None
    result = qualify(args.base_url, args.topic, payload, args.roundtrip_output)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
