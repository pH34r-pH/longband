#!/usr/bin/env python3
"""Convert cargo-mutants 27.x outcomes into a validated Stryker v2 report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft7Validator


SCHEMA_PATH = Path(__file__).parent / "schemas" / "mutation-testing-report-schema.json"
SCHEMA_VERSION = "2.0.0"
THRESHOLDS = {"high": 80, "low": 60}

SUMMARY_TO_STATUS = {
    "CaughtMutant": "Killed",
    "MissedMutant": "Survived",
    "Unviable": "CompileError",
    "Timeout": "Timeout",
    "Failure": "RuntimeError",
    # cargo-mutants only reports Success for a mutant if no test phase ran;
    # classify it as pending instead of claiming the mutant survived.
    "Success": "Pending",
}


class ReportConversionError(ValueError):
    """Raised when cargo-mutants output cannot be mapped without guessing."""


def _required_string(record: dict[str, Any], field: str, context: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ReportConversionError(f"{context} must contain a non-empty string {field!r}")
    return value


def _safe_relative_path(raw_path: str, context: str) -> PurePosixPath:
    path = PurePosixPath(raw_path.replace("\\", "/"))
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ReportConversionError(f"{context} contains an unsafe relative path: {raw_path!r}")
    return path


def _load_source(source_root: Path, raw_file: str) -> tuple[str, PurePosixPath]:
    relative_file = _safe_relative_path(raw_file, "mutant file")
    root = source_root.resolve(strict=True)
    source_path = (root / Path(*relative_file.parts)).resolve(strict=True)
    if not source_path.is_relative_to(root) or not source_path.is_file():
        raise ReportConversionError(f"mutant source is not a file below --source-root: {raw_file!r}")
    return source_path.read_text(encoding="utf-8"), relative_file


def _scenario_mutant(outcome: Any, index: int) -> dict[str, Any] | None:
    context = f"outcome {index}"
    if not isinstance(outcome, dict):
        raise ReportConversionError(f"{context} must be an object")
    scenario = outcome.get("scenario")
    if scenario == "Baseline":
        return None
    if not isinstance(scenario, dict) or set(scenario) != {"Mutant"}:
        raise ReportConversionError(f"{context} has an unrecognized cargo-mutants scenario")
    mutant = scenario["Mutant"]
    if not isinstance(mutant, dict):
        raise ReportConversionError(f"{context} mutant must be an object")
    return mutant


def validate_report(report: dict[str, Any]) -> None:
    """Validate a report against the vendored Stryker mutation schema v2.0.5."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    errors = sorted(Draft7Validator(schema).iter_errors(report), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "<root>"
        raise ReportConversionError(f"generated report fails the Stryker v2 schema at {location}: {first.message}")


def _map_mutant_outcome(
    outcome: dict[str, Any],
    mutant: dict[str, Any],
    index: int,
    source_root: Path,
    prefix: PurePosixPath,
) -> tuple[str, str, dict[str, Any]]:
    context = f"mutant outcome {index}"
    summary = _required_string(outcome, "summary", context)
    status = SUMMARY_TO_STATUS.get(summary)
    if status is None:
        raise ReportConversionError(f"{context} has unknown cargo-mutants summary {summary!r}")

    raw_file = _required_string(mutant, "file", context)
    source, relative_file = _load_source(source_root, raw_file)
    span = mutant.get("span")
    if not isinstance(span, dict) or not isinstance(span.get("start"), dict) or not isinstance(span.get("end"), dict):
        raise ReportConversionError(f"{context} must contain a start/end source span")
    genre = _required_string(mutant, "genre", context)
    name = _required_string(mutant, "name", context)
    replacement = mutant.get("replacement")
    if not isinstance(replacement, str):
        raise ReportConversionError(f"{context} replacement must be a string")

    canonical_mutant = json.dumps(mutant, sort_keys=True, separators=(",", ":"))
    result = {
        "id": hashlib.sha256(canonical_mutant.encode("utf-8")).hexdigest(),
        "mutatorName": genre,
        "description": name,
        "replacement": replacement,
        "location": span,
        "status": status,
    }
    if summary == "Success":
        result["statusReason"] = "cargo-mutants reported success without a test-phase result."
    return (prefix / relative_file).as_posix(), source, result


def convert_outcomes(
    native_report: dict[str, Any], source_root: Path, file_prefix: str = "prototype/openmls"
) -> dict[str, Any]:
    """Map a cargo-mutants outcomes.json object to the standard Stryker v2 contract."""
    if not isinstance(native_report, dict):
        raise ReportConversionError("cargo-mutants report must be a JSON object")
    version = _required_string(native_report, "cargo_mutants_version", "cargo-mutants report")
    outcomes = native_report.get("outcomes")
    if not isinstance(outcomes, list):
        raise ReportConversionError("cargo-mutants report must contain an outcomes array")

    prefix = PurePosixPath()
    if file_prefix:
        prefix = _safe_relative_path(file_prefix, "file prefix")

    files: dict[str, dict[str, Any]] = {}
    seen_ids: set[str] = set()
    mutant_count = 0
    for index, outcome in enumerate(outcomes):
        mutant = _scenario_mutant(outcome, index)
        if mutant is None:
            continue
        mutant_count += 1
        report_file, source, result = _map_mutant_outcome(outcome, mutant, index, source_root, prefix)
        mutant_id = result["id"]
        if mutant_id in seen_ids:
            raise ReportConversionError(f"cargo-mutants report repeats mutant {result['description']!r}")
        seen_ids.add(mutant_id)
        file_result = files.setdefault(
            report_file,
            {"language": "rust", "source": source, "mutants": []},
        )
        if file_result["source"] != source:
            raise ReportConversionError(f"source for {report_file!r} changed during conversion")
        file_result["mutants"].append(result)

    expected_count = native_report.get("total_mutants")
    if not isinstance(expected_count, int) or isinstance(expected_count, bool) or expected_count != mutant_count:
        raise ReportConversionError(
            f"cargo-mutants total_mutants does not match outcomes ({expected_count!r} != {mutant_count})"
        )

    report = {
        "schemaVersion": SCHEMA_VERSION,
        "thresholds": THRESHOLDS,
        "framework": {"name": "cargo-mutants", "version": version},
        "files": files,
    }
    validate_report(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="cargo-mutants outcomes.json")
    parser.add_argument("--source-root", type=Path, required=True, help="crate root used by cargo-mutants file paths")
    parser.add_argument("--file-prefix", default="prototype/openmls", help="repository-relative report path prefix")
    parser.add_argument("--output", type=Path, required=True, help="destination Stryker v2 JSON report")
    args = parser.parse_args()

    try:
        native_report = json.loads(args.input.read_text(encoding="utf-8"))
        report = convert_outcomes(native_report, args.source_root, args.file_prefix)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ReportConversionError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
