#!/usr/bin/env python3
"""Analyze a bounded synthetic or operator-supplied network capture offline.

The result covers only the supplied bytes and decoded TCP streams. It is not an
operator-opacity verdict. Raw capture, stream contents and canary stay private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import threading
import time

MAX_BYTES = 128 * 1024 * 1024
MAX_STREAMS = 256
MAX_ARTIFACTS = 32
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_OUTPUT = 64 * 1024 * 1024
MAX_SECONDS = 300


class Incomplete(ValueError):
    """The input or decoder could not establish the declared scan scope."""


class DetectedIncomplete(Incomplete):
    """A canary was seen before the remaining coverage became incomplete."""


def scan_file(path: pathlib.Path, needle: bytes, deadline: float | None = None) -> tuple[str, bool, int]:
    if path.is_symlink() or not path.is_file():
        raise Incomplete("input is not a regular file")
    before = path.stat()
    if not 0 < before.st_size <= MAX_BYTES:
        raise Incomplete("input is empty or exceeds the read budget")
    digest, overlap, total, found = hashlib.sha256(), b"", 0, False
    try:
        with path.open("rb") as src:
            while chunk := src.read(1024 * 1024):
                if deadline is not None and time.monotonic() >= deadline:
                    raise Incomplete("analysis time budget exceeded")
                digest.update(chunk)
                total += len(chunk)
                data = overlap + chunk
                found |= needle in data
                if total > MAX_BYTES:
                    raise Incomplete("input exceeded the read budget")
                overlap = data[-(len(needle) - 1):] if len(needle) > 1 else b""
        after = path.stat()
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if total != before.st_size or path.is_symlink() or any(getattr(before, n) != getattr(after, n) for n in fields):
            raise Incomplete("input changed or could not be read completely")
    except (OSError, Incomplete) as exc:
        if found:
            raise DetectedIncomplete("canary found before file scan became incomplete") from exc
        raise
    return digest.hexdigest(), found, total


def tshark(args: list[str], deadline: float | None = None) -> bytes:
    remaining = 120 if deadline is None else min(120, deadline - time.monotonic())
    if remaining <= 0:
        raise Incomplete("analysis time budget exceeded")
    try:
        process = subprocess.Popen(["tshark", "-n", *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise Incomplete("decoder unavailable") from exc
    chunks, size, exceeded = [], 0, False

    def drain() -> None:
        nonlocal size, exceeded
        try:
            while chunk := process.stdout.read(65536):
                size += len(chunk)
                if size > MAX_OUTPUT:
                    exceeded = True
                    process.kill()
                    return
                chunks.append(chunk)
        except OSError:
            exceeded = True

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        result = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        reader.join()
        process.stdout.close()
        raise Incomplete("decoder timed out") from exc
    reader.join()
    process.stdout.close()
    if result != 0 or exceeded:
        raise Incomplete("decoder failed or exceeded output budget")
    return b"".join(chunks)


def decoder_version(deadline: float | None = None) -> str:
    lines = tshark(["--version"], deadline).splitlines()
    if not lines:
        raise Incomplete("decoder version unavailable")
    line = lines[0]
    match = re.fullmatch(rb"TShark \(Wireshark\) ([0-9]+(?:\.[0-9]+){1,3})(?:[ .(+~\-].*)?", line)
    if not match:
        raise Incomplete("unrecognized decoder version")
    return match.group(1).decode("ascii")


def capture_inventory(path: pathlib.Path, deadline: float | None = None) -> tuple[int, list[int], dict]:
    raw = tshark(["-r", str(path), "-T", "fields", "-e", "frame.number", "-e", "frame.cap_len",
                  "-e", "frame.len", "-e", "tcp.stream", "-e", "tcp.analysis.lost_segment",
                  "-e", "_ws.malformed", "-e", "frame.time_epoch", "-e", "ip.src", "-e", "ipv6.src",
                  "-e", "tcp.srcport", "-e", "udp.srcport", "-e", "tls.record.content_type",
                  "-e", "tls.handshake.type", "-E", "separator=,", "-E", "occurrence=f"], deadline)
    streams, frames = set(), 0
    metadata = {"frameLengths": False, "timestamps": False, "networkAddresses": False,
                "transportPorts": False, "tlsRecordTypes": False, "tlsHandshakeTypes": False}
    for line in raw.decode("ascii").splitlines():
        row = line.split(",")
        if len(row) != 13 or not all(x.isdecimal() for x in row[:3]):
            raise Incomplete("invalid frame inventory")
        if int(row[1]) != int(row[2]) or row[4] or row[5]:
            raise Incomplete("truncated, missing or malformed packet")
        if row[3]:
            if not row[3].isdecimal():
                raise Incomplete("invalid stream identity")
            streams.add(int(row[3]))
        metadata["frameLengths"] = True
        metadata["timestamps"] |= bool(row[6])
        metadata["networkAddresses"] |= bool(row[7] or row[8])
        metadata["transportPorts"] |= bool(row[9] or row[10])
        metadata["tlsRecordTypes"] |= bool(row[11])
        metadata["tlsHandshakeTypes"] |= bool(row[12])
        frames += 1
    if not frames or len(streams) > MAX_STREAMS:
        raise Incomplete("empty capture or stream budget exceeded")
    return frames, sorted(streams), metadata


def scan_tcp_stream(path: pathlib.Path, stream: int, needle: bytes, deadline: float | None = None) -> bool:
    output = tshark(["-r", str(path), "-q", "-z", f"follow,tcp,raw,{stream}"], deadline)
    if b"Follow: tcp,raw" not in output or f"Filter: tcp.stream eq {stream}".encode() not in output:
        raise Incomplete("decoder did not return the requested stream")
    overlap = [b"", b""]
    nodes = 0
    found = False
    for line in output.splitlines():
        direction = int(line.startswith(b"\t"))
        value = line.strip()
        if not value or value.startswith((b"=", b"Follow:", b"Filter:")):
            continue
        if value.startswith((b"Node 0:", b"Node 1:")):
            nodes += 1
            continue
        if not re.fullmatch(rb"[0-9a-fA-F]+", value):
            if found:
                raise DetectedIncomplete("canary found before stream parsing failed")
            raise Incomplete("unexpected stream output")
        try:
            data = overlap[direction] + bytes.fromhex(value.decode("ascii"))
        except ValueError as exc:
            if found:
                raise DetectedIncomplete("canary found before stream parsing failed") from exc
            raise Incomplete("invalid stream data") from exc
        found |= needle in data
        overlap[direction] = data[-(len(needle) - 1):] if len(needle) > 1 else b""
    if nodes != 2 and found:
        raise DetectedIncomplete("canary found before stream parsing failed")
    if nodes != 2:
        raise Incomplete("stream endpoints unavailable")
    return found


def analyze(capture: pathlib.Path, artifacts: list[pathlib.Path], needle: bytes, source_sha: str, run_id: str) -> dict:
    if not 8 <= len(needle) <= 256 or not 1 <= len(artifacts) <= MAX_ARTIFACTS:
        raise Incomplete("canary and additional operator artifacts are required")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha) or not re.fullmatch(r"[1-9][0-9]{0,19}", run_id):
        raise Incomplete("exact source and qualification identities are required")
    deadline = time.monotonic() + MAX_SECONDS
    version = decoder_version(deadline)
    digest, found, size = scan_file(capture, needle, deadline)
    try:
        frames, streams, metadata = capture_inventory(capture, deadline)
        for stream in streams:
            found |= scan_tcp_stream(capture, stream, needle, deadline)
        # Verify the capture was not replaced while TShark analyzed it.
        if scan_file(capture, needle, deadline)[0] != digest:
            raise Incomplete("capture changed during analysis")
        artifact_digests = []
        total = size * 2
        for artifact in artifacts:
            artifact_digest, hit, artifact_size = scan_file(artifact, needle, deadline)
            found |= hit
            total += artifact_size
            if total > MAX_TOTAL_BYTES:
                raise Incomplete("aggregate input budget exceeded")
            artifact_digests.append(artifact_digest)
        if time.monotonic() >= deadline:
            raise Incomplete("analysis time budget exceeded")
    except (Incomplete, OSError, UnicodeError) as exc:
        if found or isinstance(exc, DetectedIncomplete):
            raise DetectedIncomplete("canary found before coverage became incomplete") from exc
        raise
    return {"schemaVersion": 1, "status": "found" if found else "not-found-in-supplied-bytes",
            "captureSha256": digest, "captureBytes": size, "frameCount": frames,
            "tcpStreamCount": len(streams), "artifactSha256": artifact_digests,
            "declaredSourceCommit": source_sha, "declaredQualificationRun": run_id, "tsharkVersion": version,
            "visibleMetadataCategories": metadata, "relayIdentifiers": "not-assessed",
            "scope": "supplied raw bytes and decoded TCP streams only",
            "limitations": ["Source and run identifiers are caller-supplied, not independently verified.",
                            "Capture completeness, TLS decryption, compressed application data, and unsupplied artifacts are not established.",
                            "Metadata remains visible; this is not proof of confidentiality."]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=pathlib.Path)
    parser.add_argument("--artifact", type=pathlib.Path, action="append", required=True)
    parser.add_argument("--canary-file", type=pathlib.Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        if args.canary_file.is_symlink() or not args.canary_file.is_file() or not 8 <= args.canary_file.stat().st_size <= 256:
            raise Incomplete("invalid canary file")
        with args.canary_file.open("rb") as source:
            needle = source.read(257)
        if not 8 <= len(needle) <= 256:
            raise Incomplete("invalid canary file")
        report = analyze(args.capture, args.artifact, needle, args.source_sha, args.run_id)
    except DetectedIncomplete:
        report = {"schemaVersion": 1, "status": "found", "coverage": "incomplete",
                  "declaredSourceCommit": args.source_sha, "declaredQualificationRun": args.run_id,
                  "scope": "canary detected before analysis became incomplete"}
    except (Incomplete, OSError, UnicodeError):
        raise SystemExit("network capture analysis incomplete") from None
    try:
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(report, out, sort_keys=True, indent=2)
            out.write("\n")
    except OSError:
        raise SystemExit("could not create network capture receipt") from None
    if report["status"] == "found":
        raise SystemExit("canary found in supplied capture or artifacts")


if __name__ == "__main__":
    main()
