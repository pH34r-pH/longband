"""Synthetic network-capture tests; no live network or endpoint secrets."""
import importlib.util
import io
import json
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = pathlib.Path(__file__).with_name("analyze_network_capture.py")
SOURCE = "a" * 40
RUN = "123"
spec = importlib.util.spec_from_file_location("network_capture", SCRIPT)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


def frame(seq, flags, data=b""):
    ethernet = bytes.fromhex("00112233445566778899aabb0800")
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40 + len(data), 1, 0, 64, 6, 0,
                     bytes([192, 0, 2, 1]), bytes([192, 0, 2, 2]))
    tcp = struct.pack("!HHIIBBHHH", 12345, 443, seq, 1, 0x50, flags, 65535, 0, 0)
    return ethernet + ip + tcp + data


def capture(path, *, truncated=False, gap=False):
    packets = [frame(100, 2), frame(101, 0x18, b"hello LBOPA"), frame(500 if gap else 112, 0x18, b"CITY-123- end")]
    with path.open("wb") as out:
        out.write(struct.pack("<IHHIIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))
        for index, item in enumerate(packets):
            original = len(item) + (1 if truncated and index == 1 else 0)
            out.write(struct.pack("<IIII", 1700000000, 0, len(item), original))
            out.write(item)


class NetworkCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.pcap = self.root / "test.pcap"
        self.log = self.root / "operator.log"
        capture(self.pcap)
        self.log.write_bytes(b"synthetic operator log")

    def test_missing_artifacts_and_empty_input_are_incomplete(self):
        with self.assertRaises(scanner.Incomplete):
            scanner.analyze(self.pcap, [], b"needle-123", SOURCE, RUN)
        empty = self.root / "empty"
        empty.touch()
        with self.assertRaises(scanner.Incomplete):
            scanner.scan_file(empty, b"needle")

    def test_decoder_failures_do_not_emit_negative_result(self):
        with patch.object(scanner.subprocess, "Popen", side_effect=FileNotFoundError), self.assertRaises(scanner.Incomplete):
            scanner.analyze(self.pcap, [self.log], b"needle-123", SOURCE, RUN)
        with patch.object(scanner, "tshark", return_value=b"1,4,5,0,,\n"), self.assertRaises(scanner.Incomplete):
            scanner.capture_inventory(self.pcap)
        with self.assertRaises(scanner.Incomplete):
            scanner.analyze(self.pcap, [self.log], b"needle-123", "main", RUN)
        with patch.object(scanner, "tshark", return_value=b""), self.assertRaises(scanner.Incomplete):
            scanner.decoder_version()
        with patch.object(scanner, "tshark", return_value=b"TShark (Wireshark) 4.2.2 (Git v4.2.2)\n"):
            self.assertEqual(scanner.decoder_version(), "4.2.2")
        with patch.object(scanner, "MAX_SECONDS", 0), self.assertRaises(scanner.Incomplete):
            scanner.analyze(self.pcap, [self.log], b"needle-123", SOURCE, RUN)
        with patch.object(scanner, "MAX_BYTES", 1), self.assertRaises(scanner.Incomplete):
            scanner.scan_file(self.pcap, b"needle")

    def test_file_match_across_read_boundary(self):
        data = b"x" * (1024 * 1024 - 2) + b"needle" + b"y"
        self.log.write_bytes(data)
        digest, hit, size = scanner.scan_file(self.log, b"needle")
        self.assertTrue(hit)
        self.assertEqual(size, len(data))
        self.assertEqual(len(digest), 64)

    def test_tcp_directions_are_not_joined(self):
        header = b"Follow: tcp,raw\nFilter: tcp.stream eq 0\nNode 0: a\nNode 1: b\n"
        split_directions = header + b"4c424f5041\n\t434954592d3132332d\n"
        same_direction = header + b"4c424f5041\n434954592d3132332d\n"
        with patch.object(scanner, "tshark", return_value=split_directions):
            self.assertFalse(scanner.scan_tcp_stream(self.pcap, 0, b"LBOPACITY-123-"))
        with patch.object(scanner, "tshark", return_value=same_direction):
            self.assertTrue(scanner.scan_tcp_stream(self.pcap, 0, b"LBOPACITY-123-"))
        with patch.object(scanner, "tshark", return_value=header + b"unrecognized-output\n"), self.assertRaises(scanner.Incomplete):
            scanner.scan_tcp_stream(self.pcap, 0, b"LBOPACITY-123-")
        with patch.object(scanner, "tshark", return_value=same_direction + b"unrecognized-output\n"), self.assertRaises(scanner.DetectedIncomplete):
            scanner.scan_tcp_stream(self.pcap, 0, b"LBOPACITY-123-")

    def test_file_hit_survives_later_read_failure(self):
        class BrokenReader(io.BytesIO):
            def read(self, size=-1):
                if self.tell():
                    raise OSError("synthetic read failure")
                return super().read(size)
        self.log.write_bytes(b"known-canary")
        with patch.object(pathlib.Path, "open", return_value=BrokenReader(b"known-canary")), self.assertRaises(scanner.DetectedIncomplete):
            scanner.scan_file(self.log, b"known-canary")

    @unittest.skipUnless(shutil.which("tshark"), "TShark integration required")
    def test_split_tcp_canary_and_clean_control(self):
        result = scanner.analyze(self.pcap, [self.log], b"LBOPACITY-123-", SOURCE, RUN)
        self.assertEqual(result["status"], "found")
        self.assertEqual((result["frameCount"], result["tcpStreamCount"]), (3, 1))
        self.assertTrue(result["visibleMetadataCategories"]["networkAddresses"])
        self.assertTrue(result["visibleMetadataCategories"]["transportPorts"])
        self.assertEqual(result["relayIdentifiers"], "not-assessed")
        self.assertNotIn("LBOPACITY", json.dumps(result))
        self.assertNotIn("192.0.2", json.dumps(result))
        clean = scanner.analyze(self.pcap, [self.log], b"absent-canary", SOURCE, RUN)
        self.assertEqual(clean["status"], "not-found-in-supplied-bytes")

    @unittest.skipUnless(shutil.which("tshark"), "TShark integration required")
    def test_pcapng_replay_retains_split_canary_detection(self):
        target = self.root / "test.pcapng"
        subprocess.run(["tshark", "-n", "-r", str(self.pcap), "-F", "pcapng", "-w", str(target)],
                       capture_output=True, timeout=30, check=True)
        result = scanner.analyze(target, [self.log], b"LBOPACITY-123-", SOURCE, RUN)
        self.assertEqual((result["status"], result["frameCount"]), ("found", 3))

    @unittest.skipUnless(shutil.which("tshark"), "TShark integration required")
    def test_truncated_packet_and_invalid_capture_refuse(self):
        capture(self.pcap, truncated=True)
        with self.assertRaises(scanner.Incomplete):
            scanner.analyze(self.pcap, [self.log], b"needle-123", SOURCE, RUN)
        capture(self.pcap, gap=True)
        with self.assertRaises(scanner.Incomplete):
            scanner.analyze(self.pcap, [self.log], b"needle-123", SOURCE, RUN)
        self.pcap.write_bytes(b"invalid-pcap")
        with self.assertRaises(scanner.Incomplete):
            scanner.analyze(self.pcap, [self.log], b"needle-123", SOURCE, RUN)

    @unittest.skipUnless(shutil.which("tshark"), "TShark integration required")
    def test_cli_emits_sanitized_found_receipt_and_never_overwrites(self):
        canary = self.root / "canary"
        canary.write_bytes(b"LBOPACITY-123-")
        output = self.root / "report.json"
        command = [sys.executable, str(SCRIPT), str(self.pcap), "--artifact", str(self.log),
                   "--canary-file", str(canary), "--source-sha", SOURCE, "--run-id", RUN, "--output", str(output)]
        result = subprocess.run(command, capture_output=True, check=False, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(output.read_text())["status"], "found")
        self.assertNotIn(canary.read_bytes(), result.stderr)
        original = output.read_bytes()
        self.assertNotEqual(subprocess.run(command, capture_output=True, check=False, timeout=30).returncode, 0)
        self.assertEqual(output.read_bytes(), original)

    @unittest.skipUnless(shutil.which("tshark"), "TShark integration required")
    def test_cli_incomplete_does_not_emit_receipt(self):
        capture(self.pcap, truncated=True)
        canary = self.root / "canary"
        canary.write_bytes(b"not-present-canary")
        output = self.root / "report.json"
        command = [sys.executable, str(SCRIPT), str(self.pcap), "--artifact", str(self.log),
                   "--canary-file", str(canary), "--source-sha", SOURCE, "--run-id", RUN, "--output", str(output)]
        result = subprocess.run(command, capture_output=True, check=False, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())
        self.assertNotIn(str(self.pcap).encode(), result.stderr)

    @unittest.skipUnless(shutil.which("tshark"), "TShark integration required")
    def test_cli_keeps_finding_when_capture_is_incomplete(self):
        capture(self.pcap, truncated=True)
        canary = self.root / "canary"
        canary.write_bytes(b"hello LBOPA")
        output = self.root / "report.json"
        command = [sys.executable, str(SCRIPT), str(self.pcap), "--artifact", str(self.log),
                   "--canary-file", str(canary), "--source-sha", SOURCE, "--run-id", RUN, "--output", str(output)]
        result = subprocess.run(command, capture_output=True, check=False, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        receipt = json.loads(output.read_text())
        self.assertEqual((receipt["status"], receipt["coverage"]), ("found", "incomplete"))
        self.assertNotIn("hello LBOPA", json.dumps(receipt))

    @unittest.skipUnless(shutil.which("tshark"), "TShark integration required")
    def test_decoder_output_budget_fails_closed(self):
        with patch.object(scanner, "MAX_OUTPUT", 1), self.assertRaises(scanner.Incomplete):
            scanner.decoder_version()
        with patch.object(scanner, "MAX_TOTAL_BYTES", 1), self.assertRaises(scanner.Incomplete):
            scanner.analyze(self.pcap, [self.log], b"needle-123", SOURCE, RUN)

    @unittest.skipUnless(shutil.which("tshark"), "TShark integration required")
    def test_artifact_finding_survives_later_missing_artifact(self):
        self.log.write_bytes(b"known-canary")
        with self.assertRaises(scanner.DetectedIncomplete):
            scanner.analyze(self.pcap, [self.log, self.root / "missing"], b"known-canary", SOURCE, RUN)


if __name__ == "__main__":
    unittest.main()
