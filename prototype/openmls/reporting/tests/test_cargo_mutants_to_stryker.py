from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft7Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cargo_mutants_to_stryker as adapter


FIXTURES = Path(__file__).parent / "fixtures"


class CargoMutantsToStrykerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.native = json.loads((FIXTURES / "native-outcomes.json").read_text(encoding="utf-8"))
        self.tempdir = tempfile.TemporaryDirectory()
        self.source_root = Path(self.tempdir.name)
        source = self.source_root / "src" / "main.rs"
        source.parent.mkdir(parents=True)
        source.write_bytes((FIXTURES / "src" / "main.rs").read_bytes())

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_maps_native_outcomes_and_validates_official_schema(self) -> None:
        report = adapter.convert_outcomes(self.native, self.source_root)
        schema = json.loads(adapter.SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
        Draft7Validator(schema).validate(report)

        self.assertEqual(report["schemaVersion"], "2.0.0")
        self.assertEqual(report["framework"], {"name": "cargo-mutants", "version": "27.1.0"})
        file_report = report["files"]["prototype/openmls/src/main.rs"]
        self.assertEqual(file_report["source"], (FIXTURES / "src" / "main.rs").read_text(encoding="utf-8"))
        self.assertEqual(
            [mutant["status"] for mutant in file_report["mutants"]],
            ["Killed", "Survived", "CompileError", "Timeout", "RuntimeError", "Pending"],
        )
        self.assertNotIn("statusReason", file_report["mutants"][0])
        self.assertIn("without a test-phase result", file_report["mutants"][-1]["statusReason"])
        self.assertEqual(len({mutant["id"] for mutant in file_report["mutants"]}), 6)
        self.assertTrue(all(mutant["mutatorName"] for mutant in file_report["mutants"]))

    def test_rejects_unknown_native_outcome(self) -> None:
        native = copy.deepcopy(self.native)
        native["outcomes"][1]["summary"] = "FutureCargoMutantsOutcome"

        with self.assertRaisesRegex(adapter.ReportConversionError, "unknown cargo-mutants summary"):
            adapter.convert_outcomes(native, self.source_root)

    def test_rejects_invalid_report_schema_version(self) -> None:
        with self.assertRaisesRegex(adapter.ReportConversionError, "fails the Stryker v2 schema"):
            adapter.validate_report({"schemaVersion": "3.0.0", "thresholds": {"high": 80, "low": 60}, "files": {}})

    def test_rejects_mismatched_native_mutant_count(self) -> None:
        native = copy.deepcopy(self.native)
        native["total_mutants"] += 1

        with self.assertRaisesRegex(adapter.ReportConversionError, "total_mutants does not match"):
            adapter.convert_outcomes(native, self.source_root)


if __name__ == "__main__":
    unittest.main()
