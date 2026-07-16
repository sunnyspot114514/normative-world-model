"""Source-lock-safe orchestration for Phase-1 v3 retained discovery."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tomllib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .audits import (
    audit_density,
    audit_model_input_integrity,
    audit_nontriviality,
    audit_split_integrity,
    audit_state_machine_integrity,
    audit_surface_leakage_by_environment,
)
from .calibration import run_calibration_cases
from .generator import (
    _digest_families,
    _load_density_gates,
    _write_dataset_card,
    _write_json,
    _write_jsonl,
    project_root,
)
from .normative_oracle import NORMATIVE_ORACLE_VERSION
from .phase1_v3 import (
    GENERATOR_REVISION,
    PREREGISTRATION_VERSION,
    SCHEMA_VERSION,
    audit_natural_language_v3,
    generate_v3_environment_families,
)
from .reachability import enumerate_reachability, render_reachability_markdown

SMOKE_RUN_KIND = "v3_internal_smoke"
RETAINED_RUN_KIND = "v3_retained_discovery"
DRY_RUN_KIND = "v3_retained_dry_run"
ACCEPTANCE_RELATIVE_PATH = Path(
    "artifacts/phase1_v3_smoke/EXTERNAL_AUDIT_ACCEPTED.json"
)
SMOKE_MANIFEST_RELATIVE_PATH = Path(
    "artifacts/phase1_v3_smoke/provenance_manifest.json"
)
SMOKE_REPORT_RELATIVE_PATH = Path(
    "artifacts/phase1_v3_smoke/phase1_exit_report.json"
)
SOURCE_LOCK_RELATIVE_PATH = Path("configs/phase1_v3_source_lock.json")
SMOKE_DATA_RELATIVE_PATH = Path("data/generated/phase1_v3_smoke")
RETAINED_DATA_RELATIVE_PATH = Path("data/generated/phase1_discovery_v3")
RETAINED_ARTIFACT_RELATIVE_PATH = Path("artifacts/phase1_v3")
DRY_RUN_DATA_RELATIVE_PATH = Path("data/generated/phase1_v3_retained_dry_run")
DRY_RUN_ARTIFACT_RELATIVE_PATH = Path("artifacts/phase1_v3_retained_dry_run")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _verify_hash_mapping(
    root: Path,
    mapping: dict[str, Any],
    *,
    label: str,
) -> list[str]:
    failures: list[str] = []
    for relative, expected in mapping.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            failures.append(f"{label} contains a non-string path or hash")
            continue
        path = root / relative
        if not path.is_file():
            failures.append(f"missing {label} path: {relative}")
            continue
        if _sha256(path) != expected.lower():
            failures.append(f"{label} hash mismatch: {relative}")
    return failures


def _normalized_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key.replace("\\", "/"): value for key, value in mapping.items()}


def validate_v3_external_acceptance(root: Path | None = None) -> list[str]:
    """Validate the exact external record and every object that it binds."""

    root = (root or project_root()).resolve()
    acceptance_path = root / ACCEPTANCE_RELATIVE_PATH
    manifest_path = root / SMOKE_MANIFEST_RELATIVE_PATH
    report_path = root / SMOKE_REPORT_RELATIVE_PATH
    source_lock_path = root / SOURCE_LOCK_RELATIVE_PATH
    required_paths = (
        acceptance_path,
        manifest_path,
        report_path,
        source_lock_path,
    )
    missing = [
        str(path.relative_to(root)).replace("\\", "/")
        for path in required_paths
        if not path.is_file()
    ]
    if missing:
        return [f"missing v3 acceptance input: {path}" for path in missing]

    try:
        acceptance = _load_json(acceptance_path)
        manifest = _load_json(manifest_path)
        report = _load_json(report_path)
        source_lock = _load_json(source_lock_path)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        return [f"invalid v3 acceptance input: {error}"]

    failures: list[str] = []
    exact_fields = {
        "status": "EXTERNAL_ACCEPTED",
        "unconditional": True,
        "preregistration_version": PREREGISTRATION_VERSION,
        "generator_revision": GENERATOR_REVISION,
        "run_kind": SMOKE_RUN_KIND,
    }
    for field, expected in exact_fields.items():
        if acceptance.get(field) != expected:
            failures.append(
                f"external acceptance {field} is {acceptance.get(field)!r}, "
                f"expected {expected!r}"
            )
    if acceptance.get("blocking_findings") != []:
        failures.append("external acceptance contains blocking findings")
    if not isinstance(acceptance.get("reviewer"), str) or not acceptance["reviewer"].strip():
        failures.append("external acceptance lacks reviewer identity")
    reviewed_at = acceptance.get("reviewed_at")
    if not isinstance(reviewed_at, str):
        failures.append("external acceptance lacks reviewed_at timestamp")
    else:
        try:
            datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
        except ValueError:
            failures.append("external acceptance reviewed_at is not ISO-8601")

    if acceptance.get("provenance_manifest_sha256") != _sha256(manifest_path):
        failures.append("external acceptance does not bind the current v3 smoke manifest")

    expected_corpus = {
        "data/generated/phase1_v3_smoke/game.jsonl",
        "data/generated/phase1_v3_smoke/organization.jsonl",
    }
    accepted_corpus = acceptance.get("corpus_sha256")
    if not isinstance(accepted_corpus, dict) or set(accepted_corpus) != expected_corpus:
        failures.append("external acceptance must bind exactly both v3 smoke corpus files")
    else:
        failures.extend(
            _verify_hash_mapping(root, accepted_corpus, label="accepted smoke corpus")
        )
        manifest_files = manifest.get("files", {})
        if not isinstance(manifest_files, dict):
            failures.append("v3 smoke manifest files section is invalid")
        else:
            normalized_manifest_files = _normalized_mapping(manifest_files)
            for relative, expected in accepted_corpus.items():
                if normalized_manifest_files.get(relative) != expected:
                    failures.append(
                        f"v3 smoke manifest does not bind accepted corpus: {relative}"
                    )

    if report.get("status") != "PASS" or report.get("run_kind") != SMOKE_RUN_KIND:
        failures.append("v3 smoke exit report is not a PASS")
    if report.get("preregistration_version") != PREREGISTRATION_VERSION:
        failures.append("v3 smoke report preregistration version mismatch")
    if report.get("generator_revision") != GENERATOR_REVISION:
        failures.append("v3 smoke report generator revision mismatch")
    if report.get("total_discovery_families") != 600:
        failures.append("v3 smoke report does not contain 600 families")
    if report.get("temporary_fixture_family_count") != 0:
        failures.append("v3 smoke report contains temporary fixtures")
    if report.get("confirmation", {}).get("status") != "RESERVED_NOT_GENERATED":
        failures.append("v3 smoke report indicates generated confirmation content")
    if report.get("internal_review", {}).get("authorizes_retained_generation") is not False:
        failures.append("v3 smoke internal review improperly authorizes retention")

    if manifest.get("run_kind") != SMOKE_RUN_KIND:
        failures.append("v3 smoke manifest run kind mismatch")
    if manifest.get("family_count") != 600:
        failures.append("v3 smoke manifest family count mismatch")
    manifest_files = manifest.get("files")
    manifest_inputs = manifest.get("inputs")
    if not isinstance(manifest_files, dict):
        failures.append("v3 smoke manifest files section is invalid")
    else:
        failures.extend(_verify_hash_mapping(root, manifest_files, label="smoke manifest file"))
    if not isinstance(manifest_inputs, dict):
        failures.append("v3 smoke manifest inputs section is invalid")
    else:
        failures.extend(
            _verify_hash_mapping(root, manifest_inputs, label="smoke manifest input")
        )

    if len(source_lock) != 29:
        failures.append(f"v3 source lock contains {len(source_lock)} entries, expected 29")
    failures.extend(_verify_hash_mapping(root, source_lock, label="v3 source lock"))
    if (
        isinstance(manifest_inputs, dict)
        and _normalized_mapping(manifest_inputs) != _normalized_mapping(source_lock)
    ):
        failures.append("v3 smoke manifest inputs differ from the 29-file source lock")
    return failures


def _preregistration(root: Path) -> dict[str, Any]:
    with (root / "configs/preregistration_v3.toml").open("rb") as handle:
        return tomllib.load(handle)


def _logical_file_hashes(
    root: Path,
    staging_data: Path,
    staging_artifacts: Path,
    data_relative: Path,
    artifact_relative: Path,
) -> dict[str, str]:
    values: dict[str, str] = {}
    for staging_root, logical_root in (
        (staging_data, data_relative),
        (staging_artifacts, artifact_relative),
    ):
        for path in sorted(staging_root.rglob("*")):
            if path.is_file() and path.name != "provenance_manifest.json":
                relative = logical_root / path.relative_to(staging_root)
                values[relative.as_posix()] = _sha256(path)
    return values


def _collect_status_failures(
    environment_reports: dict[str, Any],
    leakage: dict[str, Any],
    calibration: dict[str, Any],
    *,
    enforce_statistical_gates: bool,
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    ignored_small_sample_failures: list[str] = []
    dry_run_allowed = {
        "natural_language": {
            "noncausal prose is not scenario-dependent",
        },
        "model_input_integrity": {
            "serialized row order remains correlated with a model-input feature",
            "model input contains a near-unique scalar feature",
        },
    }
    for environment, environment_report in environment_reports.items():
        if not environment_report["replay_digest_matches"]:
            failures.append(f"{environment}: deterministic replay")
        audit_names = [
            "split_integrity",
            "state_machine_integrity",
            "natural_language",
            "model_input_integrity",
        ]
        if enforce_statistical_gates:
            audit_names.extend(["density", "nontriviality"])
        for audit_name in audit_names:
            audit = environment_report[audit_name]
            if audit["status"] != "PASS":
                for failure in audit["failures"]:
                    qualified = f"{environment}: {failure}"
                    if (
                        not enforce_statistical_gates
                        and failure in dry_run_allowed.get(audit_name, set())
                    ):
                        ignored_small_sample_failures.append(qualified)
                    else:
                        failures.append(qualified)
    if enforce_statistical_gates and leakage["status"] != "PASS":
        failures.extend(f"leakage: {failure}" for failure in leakage["failures"])
    if calibration["status"] != "PASS":
        failures.extend(
            f"calibration: {failure}" for failure in calibration["failures"]
        )
    return failures, ignored_small_sample_failures


def _promote_staging_directories(
    staging_data: Path,
    staging_artifacts: Path,
    data_dir: Path,
    artifact_dir: Path,
) -> None:
    if data_dir.exists() or artifact_dir.exists():
        raise FileExistsError(
            "refusing to overwrite an existing retained or dry-run output directory"
        )
    data_dir.parent.mkdir(parents=True, exist_ok=True)
    artifact_dir.parent.mkdir(parents=True, exist_ok=True)
    data_promoted = False
    try:
        os.replace(staging_data, data_dir)
        data_promoted = True
        os.replace(staging_artifacts, artifact_dir)
    except OSError:
        if data_promoted and data_dir.exists() and not staging_data.exists():
            os.replace(data_dir, staging_data)
        raise


def run_phase1_v3_retained(
    *,
    mode: str = "retained",
    families_per_environment: int | None = None,
    seed: int | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Generate a dry run or the accepted v3 retained discovery corpus."""

    root = (root or project_root()).resolve()
    acceptance_failures = validate_v3_external_acceptance(root)
    if acceptance_failures:
        raise RuntimeError(
            "v3 retained generation is blocked: " + "; ".join(acceptance_failures)
        )
    preregistration = _preregistration(root)
    frozen_seed = int(preregistration["seeds"]["discovery"])
    requested_seed = frozen_seed if seed is None else seed
    if requested_seed != frozen_seed:
        raise ValueError(
            f"v3 discovery seed is frozen at {frozen_seed}; received {requested_seed}"
        )

    if mode == "retained":
        expected_families = int(
            preregistration["sample_size"]["minimum_discovery_families_per_environment"]
        )
        requested_families = (
            expected_families
            if families_per_environment is None
            else families_per_environment
        )
        if requested_families != expected_families:
            raise ValueError(
                "formal retained generation requires exactly "
                f"{expected_families} families per environment"
            )
        run_kind = RETAINED_RUN_KIND
        data_relative = RETAINED_DATA_RELATIVE_PATH
        artifact_relative = RETAINED_ARTIFACT_RELATIVE_PATH
        enforce_statistical_gates = True
    elif mode == "dry-run":
        requested_families = 10 if families_per_environment is None else families_per_environment
        if not 1 <= requested_families <= 50:
            raise ValueError("dry-run families per environment must lie in [1, 50]")
        run_kind = DRY_RUN_KIND
        data_relative = DRY_RUN_DATA_RELATIVE_PATH
        artifact_relative = DRY_RUN_ARTIFACT_RELATIVE_PATH
        enforce_statistical_gates = False
    else:
        raise ValueError(f"unknown v3 retained mode: {mode}")

    data_dir = root / data_relative
    artifact_dir = root / artifact_relative
    if data_dir.exists() or artifact_dir.exists():
        raise FileExistsError(
            f"{mode} output already exists; refusing to overwrite frozen evidence"
        )

    staging_root = root / ".tmp" / "phase1_v3_retained" / (
        f"{mode}-{uuid.uuid4().hex}"
    )
    staging_data = staging_root / "data"
    staging_artifacts = staging_root / "artifacts"
    staging_data.mkdir(parents=True)
    staging_artifacts.mkdir(parents=True)

    gates = _load_density_gates()
    all_families: list[dict[str, Any]] = []
    environment_reports: dict[str, Any] = {}
    corpus_hashes: dict[str, str] = {}
    for offset, environment in enumerate(("game", "organization")):
        environment_seed = requested_seed + offset * 100_003
        families = generate_v3_environment_families(
            environment,
            requested_families,
            environment_seed,
        )
        replay = generate_v3_environment_families(
            environment,
            requested_families,
            environment_seed,
        )
        replay_match = _digest_families(families) == _digest_families(replay)
        output_path = staging_data / f"{environment}.jsonl"
        logical_path = (data_relative / f"{environment}.jsonl").as_posix()
        corpus_hashes[logical_path] = _write_jsonl(output_path, families)
        environment_reports[environment] = {
            "seed": environment_seed,
            "replay_digest_matches": replay_match,
            "density": audit_density(families, gates),
            "split_integrity": audit_split_integrity(families),
            "state_machine_integrity": audit_state_machine_integrity(families),
            "natural_language": audit_natural_language_v3(families),
            "nontriviality": audit_nontriviality(families),
            "model_input_integrity": audit_model_input_integrity(families),
        }
        all_families.extend(families)

    leakage = audit_surface_leakage_by_environment(
        all_families,
        requested_seed + 700_001,
    )
    calibration = run_calibration_cases()
    reachability_path = staging_artifacts / "uncertainty_reachability.md"
    reachability_path.write_text(
        render_reachability_markdown(enumerate_reachability(5)),
        encoding="utf-8",
    )

    smoke_confirmation = root / SMOKE_DATA_RELATIVE_PATH / "confirmation_reservation.json"
    confirmation = _load_json(smoke_confirmation)
    if confirmation.get("status") != "RESERVED_NOT_GENERATED":
        raise RuntimeError("smoke confirmation reservation is not safely reserved")
    shutil.copy2(
        smoke_confirmation,
        staging_data / "confirmation_reservation.json",
    )

    status_failures, ignored_small_sample_failures = _collect_status_failures(
        environment_reports,
        leakage,
        calibration,
        enforce_statistical_gates=enforce_statistical_gates,
    )
    acceptance_path = root / ACCEPTANCE_RELATIVE_PATH
    source_lock_path = root / SOURCE_LOCK_RELATIVE_PATH
    source_lock = _load_json(source_lock_path)
    report = {
        "schema_version": SCHEMA_VERSION,
        "preregistration_version": PREREGISTRATION_VERSION,
        "generator_revision": GENERATOR_REVISION,
        "normative_oracle_version": NORMATIVE_ORACLE_VERSION,
        "run_kind": run_kind,
        "status": "PASS" if not status_failures else "FAIL",
        "failures": status_failures,
        "ignored_small_sample_failures": ignored_small_sample_failures,
        "gate_policy": (
            "all_frozen_phase1_gates"
            if enforce_statistical_gates
            else "structural_dry_run_only"
        ),
        "families_per_environment": requested_families,
        "total_discovery_families": len(all_families),
        "temporary_fixture_family_count": sum(
            bool(family["temporary_fixture_fields"]) for family in all_families
        ),
        "environments": environment_reports,
        "surface_leakage": leakage,
        "calibration": calibration,
        "confirmation": confirmation,
        "external_acceptance": {
            "status": "VERIFIED",
            "path": ACCEPTANCE_RELATIVE_PATH.as_posix(),
            "sha256": _sha256(acceptance_path),
            "source_lock_sha256": _sha256(source_lock_path),
            "bound_smoke_manifest_sha256": _sha256(
                root / SMOKE_MANIFEST_RELATIVE_PATH
            ),
        },
        "governance": {
            "retained_discovery_authorized": mode == "retained",
            "dry_run_only": mode == "dry-run",
            "confirmation_generated": False,
            "confirmation_status": confirmation["status"],
        },
        "corpus_sha256": corpus_hashes,
    }
    _write_json(staging_artifacts / "phase1_exit_report.json", report)
    _write_dataset_card(staging_artifacts / "DATASET_CARD.md", report)

    orchestration_paths = [
        root / "src/normative_world_model/retained_v3.py",
        root / "scripts/run-phase1-v3-retained.py",
    ]
    files = _logical_file_hashes(
        root,
        staging_data,
        staging_artifacts,
        data_relative,
        artifact_relative,
    )
    manifest = {
        "generator_schema_version": SCHEMA_VERSION,
        "preregistration_version": PREREGISTRATION_VERSION,
        "generator_revision": GENERATOR_REVISION,
        "normative_oracle_version": NORMATIVE_ORACLE_VERSION,
        "run_kind": run_kind,
        "seed": requested_seed,
        "family_count": len(all_families),
        "family_count_scope": "combined across environments",
        "families_per_environment": {
            environment: requested_families for environment in environment_reports
        },
        "files": files,
        "frozen_inputs": source_lock,
        "orchestration_inputs": {
            path.relative_to(root).as_posix(): _sha256(path)
            for path in orchestration_paths
        },
        "external_acceptance": {
            ACCEPTANCE_RELATIVE_PATH.as_posix(): _sha256(acceptance_path),
            SMOKE_MANIFEST_RELATIVE_PATH.as_posix(): _sha256(
                root / SMOKE_MANIFEST_RELATIVE_PATH
            ),
            SOURCE_LOCK_RELATIVE_PATH.as_posix(): _sha256(source_lock_path),
        },
        "governance": report["governance"],
    }
    _write_json(staging_artifacts / "provenance_manifest.json", manifest)

    if report["status"] != "PASS":
        report["staging_path"] = str(staging_root)
        return report

    _promote_staging_directories(
        staging_data,
        staging_artifacts,
        data_dir,
        artifact_dir,
    )
    try:
        staging_root.rmdir()
        staging_root.parent.rmdir()
    except OSError:
        pass
    report["data_dir"] = data_relative.as_posix()
    report["artifact_dir"] = artifact_relative.as_posix()
    return report


def verify_v3_retained_artifacts(
    root: Path | None = None,
    *,
    require_retained: bool = True,
) -> list[str]:
    """Verify the promoted retained corpus, its report, and provenance."""

    root = (root or project_root()).resolve()
    failures = validate_v3_external_acceptance(root)
    artifact_dir = root / RETAINED_ARTIFACT_RELATIVE_PATH
    data_dir = root / RETAINED_DATA_RELATIVE_PATH
    if not artifact_dir.exists() and not data_dir.exists():
        if require_retained:
            failures.append("v3 retained discovery artifacts are missing")
        return failures
    if not artifact_dir.is_dir() or not data_dir.is_dir():
        failures.append("v3 retained discovery is only partially promoted")
        return failures

    manifest_path = artifact_dir / "provenance_manifest.json"
    report_path = artifact_dir / "phase1_exit_report.json"
    if not manifest_path.is_file() or not report_path.is_file():
        failures.append("v3 retained manifest or report is missing")
        return failures
    try:
        manifest = _load_json(manifest_path)
        report = _load_json(report_path)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        failures.append(f"invalid v3 retained artifact: {error}")
        return failures

    for section in ("files", "frozen_inputs", "orchestration_inputs", "external_acceptance"):
        mapping = manifest.get(section)
        if not isinstance(mapping, dict):
            failures.append(f"v3 retained manifest {section} section is invalid")
        else:
            failures.extend(
                _verify_hash_mapping(root, mapping, label=f"retained {section}")
            )
    if report.get("status") != "PASS" or report.get("run_kind") != RETAINED_RUN_KIND:
        failures.append("v3 retained exit report is not a PASS")
    if report.get("total_discovery_families") != 2000:
        failures.append("v3 retained corpus does not contain 2,000 families")
    if report.get("families_per_environment") != 1000:
        failures.append("v3 retained corpus does not contain 1,000 families per environment")
    if report.get("temporary_fixture_family_count") != 0:
        failures.append("v3 retained corpus contains temporary fixtures")
    if report.get("confirmation", {}).get("status") != "RESERVED_NOT_GENERATED":
        failures.append("confirmation content was unexpectedly generated")
    if report.get("governance", {}).get("confirmation_generated") is not False:
        failures.append("retained report has invalid confirmation governance")
    if manifest.get("run_kind") != RETAINED_RUN_KIND:
        failures.append("v3 retained manifest run kind mismatch")
    if manifest.get("family_count") != 2000:
        failures.append("v3 retained manifest family count mismatch")
    return failures
