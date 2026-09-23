"""Trust-boundary tests for the public Alpha package producer."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("build_offline_package.py")
SPEC = importlib.util.spec_from_file_location("build_offline_package", SCRIPT)
package = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(package)
SHA = "a" * 40


class PackageBoundaryTests(unittest.TestCase):
    def test_rejects_wrong_checkout_or_origin(self) -> None:
        with patch.object(package.subprocess, "check_output", return_value=SHA + "\n"):
            with self.assertRaisesRegex(package.PackageError, "exact requested"):
                package.identity(Path("."), {"GITHUB_SHA": "b" * 40})
            with self.assertRaisesRegex(package.PackageError, "repository differs"):
                package.identity(Path("."), {"GITHUB_REPOSITORY": "attacker/longband"})
            with self.assertRaisesRegex(package.PackageError, "originate on main"):
                package.identity(Path("."), {"GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/topic"})

    def test_source_archive_extraction_rejects_links_and_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "source.tar.gz"
            for malicious in (f"longband-{SHA}/../../escape", f"longband-{SHA}/shortcut"):
                with tarfile.open(archive, "w:gz") as tar:
                    entry = tarfile.TarInfo(malicious)
                    if malicious.endswith("shortcut"):
                        entry.type = tarfile.SYMTYPE
                        entry.linkname = "/etc/passwd"
                    else:
                        entry.size = 1
                    tar.addfile(entry, io.BytesIO(b"X") if entry.isfile() else None)
                with self.assertRaisesRegex(package.PackageError, "unsafe"):
                    package.extract_exact_source(archive, SHA, root / "extracted")

    def test_bundle_records_actual_bytes_and_rejects_linked_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / f"longband-{SHA}-source.tar.gz"
            archive.write_bytes(b"checked source archive")
            unit = root / "longband-alpha.service"
            unit.write_bytes(b"[Service]\nUser=longband\n")
            wheels = root / "wheels"
            wheels.mkdir()
            wheel = wheels / "longband_relay-0.1.0-py3-none-any.whl"
            wheel.write_bytes(b"a wheel installed by the builder")
            source = {
                "repository": package.REPOSITORY, "sha": SHA, "ref": "refs/heads/main",
                "event": "push", "workflow": package.WORKFLOW, "job": "package",
                "workflowPath": ".github/workflows/python-alpha.yml",
                "runId": 123, "runAttempt": 1,
                "artifactName": f"longband-offline-package-{SHA}-123-1",
            }
            output = root / "output"
            receipt = package.make_bundle(source, archive, unit, wheels, output)
            bundle = output / receipt["bundle"]["filename"]
            self.assertEqual(package.digest_file(bundle), receipt["bundle"]["sha256"])
            self.assertEqual(bundle.stat().st_size, receipt["bundle"]["sizeBytes"])
            self.assertEqual(json.loads((output / "package-receipt.json").read_text()), receipt)
            with tarfile.open(bundle, "r:gz") as tar:
                members = {member.name: tar.extractfile(member).read() for member in tar}
            manifest = json.loads(members["manifest.json"])
            self.assertEqual(manifest, {key: value for key, value in receipt.items() if key != "bundle"})
            content = [
                {"path": f"source/{archive.name}", **manifest["sourceArchive"]},
                {"path": "deploy/longband-alpha.service", **manifest["serviceUnit"]},
                {"path": f"wheelhouse/{wheel.name}", **manifest["wheels"][0]},
            ]
            content.sort(key=lambda entry: entry["path"])
            self.assertEqual(hashlib.sha256(json.dumps(content, sort_keys=True,
                separators=(",", ":")).encode()).hexdigest(), manifest["contentSha256"])
            for name, record in (
                (f"source/{archive.name}", manifest["sourceArchive"]),
                ("deploy/longband-alpha.service", manifest["serviceUnit"]),
                (f"wheelhouse/{wheel.name}", manifest["wheels"][0]),
            ):
                self.assertEqual(hashlib.sha256(members[name]).hexdigest(), record["sha256"])
                self.assertEqual(len(members[name]), record["sizeBytes"])
            wheel.unlink()
            wheel.symlink_to(unit)
            with self.assertRaisesRegex(package.PackageError, "linked wheels"):
                package.make_bundle(source, archive, unit, wheels, root / "other")


if __name__ == "__main__":
    unittest.main()
