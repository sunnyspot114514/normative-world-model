"""Frozen Phase-2 retained baseline and model-arm export orchestration."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import subprocess
import tomllib
import uuid
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType
from typing import Any

from .baselines import run_smoke_baselines
from .model_arms import (
    build_factorized_factual_records,
    build_factorized_normative_records,
    build_joint_records,
    evaluator_visibility_failures,
)
from .retained_v3 import verify_v3_retained_artifacts
from .transfer_matrix import build_transfer_manifest

CONFIG_RELATIVE_PATH = Path("configs/phase2_retained.toml")
PHASE1_DATA_RELATIVE_PATH = Path("data/generated/phase1_discovery_v3")
PHASE1_ARTIFACT_RELATIVE_PATH = Path("artifacts/phase1_v3")
PHASE2_DATA_RELATIVE_PATH = Path("data/generated/phase2_retained/arms")
PHASE2_ARTIFACT_RELATIVE_PATH = Path("artifacts/phase2_retained")
RUN_KIND = "phase2_retained_discovery"

SOURCE_PATHS = {
    "phase1_provenance_manifest": Path(
        "artifacts/phase1_v3/provenance_manifest.json"
    ),
    "phase1_exit_report": Path("artifacts/phase1_v3/phase1_exit_report.json"),
    "game_jsonl": Path("data/generated/phase1_discovery_v3/game.jsonl"),
    "organization_jsonl": Path(
        "data/generated/phase1_discovery_v3/organization.jsonl"
    ),
    "confirmation_reservation": Path(
        "data/generated/phase1_discovery_v3/confirmation_reservation.json"
    ),
    "external_acceptance": Path(
        "artifacts/phase1_v3_smoke/EXTERNAL_AUDIT_ACCEPTED.json"
    ),
    "phase1_source_lock": Path("configs/phase1_v3_source_lock.json"),
}

PHASE2_INPUT_PATHS = (
    CONFIG_RELATIVE_PATH,
    Path("scripts/run-phase2-retained.py"),
    Path("scripts/run-phase2-internal-check.py"),
    Path("src/normative_world_model/__init__.py"),
    Path("src/normative_world_model/audits.py"),
    Path("src/normative_world_model/phase2_retained.py"),
    Path("src/normative_world_model/baselines.py"),
    Path("src/normative_world_model/bootstrap.py"),
    Path("src/normative_world_model/comparators.py"),
    Path("src/normative_world_model/contracts.py"),
    Path("src/normative_world_model/metrics.py"),
    Path("src/normative_world_model/model_arms.py"),
    Path("src/normative_world_model/model_output.py"),
    Path("src/normative_world_model/phase2_dataset.py"),
    Path("src/normative_world_model/phase2_metrics.py"),
    Path("src/normative_world_model/policy_oracle.py"),
    Path("src/normative_world_model/transfer_matrix.py"),
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _write_json(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return _sha256(path)


def _load_config(root: Path) -> dict[str, Any]:
    with (root / CONFIG_RELATIVE_PATH).open("rb") as handle:
        return tomllib.load(handle)


def _load_families(data_dir: Path) -> list[dict[str, Any]]:
    families: list[dict[str, Any]] = []
    for environment in ("game", "organization"):
        path = data_dir / f"{environment}.jsonl"
        families.extend(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        )
    return families


def _id_hash(values: Iterable[str]) -> str:
    preimage = "".join(f"{value}\n" for value in sorted(values))
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def _split_bindings(families: list[dict[str, Any]]) -> dict[str, Any]:
    bindings: dict[str, Any] = {}
    for environment in ("game", "organization"):
        rows = [row for row in families if row["environment"] == environment]
        bindings[environment] = {}
        for split in ("train", "development"):
            ids = [row["scenario_id"] for row in rows if row["split"] == split]
            bindings[environment][split] = {
                "scenario_count": len(ids),
                "scenario_ids_sha256": _id_hash(ids),
            }
    return bindings


def _smoke_overlap(root: Path, families: list[dict[str, Any]]) -> dict[str, Any]:
    retained = {
        environment: {
            row["scenario_id"]: row
            for row in families
            if row["environment"] == environment
        }
        for environment in ("game", "organization")
    }
    result: dict[str, Any] = {}
    for environment in ("game", "organization"):
        smoke_path = root / "data/generated/phase1_v3_smoke" / f"{environment}.jsonl"
        smoke_rows = [
            json.loads(line)
            for line in smoke_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        overlap_ids = sorted(
            row["scenario_id"]
            for row in smoke_rows
            if row["scenario_id"] in retained[environment]
        )
        exact_equal = sum(
            row == retained[environment][row["scenario_id"]]
            for row in smoke_rows
            if row["scenario_id"] in retained[environment]
        )
        result[environment] = {
            "smoke_family_count": len(smoke_rows),
            "retained_family_count": len(retained[environment]),
            "overlap_family_count": len(overlap_ids),
            "exact_equal_overlap_count": exact_equal,
            "overlap_scenario_ids_sha256": _id_hash(overlap_ids),
            "retained_overlap_fraction": (
                len(overlap_ids) / len(retained[environment])
            ),
            "independent_confirmation": False,
        }
    return result


def validate_phase2_retained_inputs(root: Path | None = None) -> list[str]:
    """Validate the accepted Phase-1 corpus and the frozen Phase-2 source lock."""

    root = (root or project_root()).resolve()
    failures = verify_v3_retained_artifacts(root, require_retained=True)
    try:
        config = _load_config(root)
    except (OSError, tomllib.TOMLDecodeError) as error:
        return [*failures, f"invalid Phase-2 retained config: {error}"]

    exact_fields = {
        "version": "1.0-retained",
        "status": "frozen_before_phase2_retained_baseline",
        "run_kind": RUN_KIND,
        "source_data_dir": PHASE1_DATA_RELATIVE_PATH.as_posix(),
        "source_artifact_dir": PHASE1_ARTIFACT_RELATIVE_PATH.as_posix(),
        "output_data_dir": PHASE2_DATA_RELATIVE_PATH.as_posix(),
        "output_artifact_dir": PHASE2_ARTIFACT_RELATIVE_PATH.as_posix(),
        "families_per_environment": 1000,
        "total_families": 2000,
        "smoke_overlap_families_per_environment": 300,
        "confirmation_status": "RESERVED_NOT_GENERATED",
        "retained_discovery_is_independent_confirmation": False,
    }
    for field, expected in exact_fields.items():
        if config.get(field) != expected:
            failures.append(
                f"Phase-2 retained config {field} is {config.get(field)!r}, "
                f"expected {expected!r}"
            )
    governance = config.get("governance", {})
    required_governance = {
        "phase1_retained_required": True,
        "phase1_smoke_default_forbidden": True,
        "overwrite_existing_outputs": False,
        "confirmation_generation_authorized": False,
        "model_training_authorized": False,
        "h5_rollout_status": "UNIDENTIFIED",
    }
    for field, expected in required_governance.items():
        if governance.get(field) != expected:
            failures.append(
                f"Phase-2 retained governance {field} is not {expected!r}"
            )
    expected_bootstrap = {
        "samples": 5000,
        "confidence_level": 0.95,
        "seed": 20260916,
        "effective_unit": "scenario_family",
    }
    if config.get("bootstrap") != expected_bootstrap:
        failures.append("Phase-2 retained bootstrap contract changed")
    expected_exports = {
        "include_stored_rollout": True,
        "joint_views": ["joint_naive", "joint_consistency"],
        "factorized_views": [
            "factorized_factual",
            "factorized_normative",
        ],
        "gzip_mtime": 0,
    }
    if config.get("exports") != expected_exports:
        failures.append("Phase-2 retained export contract changed")

    source_hashes = config.get("source_hashes", {})
    if set(source_hashes) != set(SOURCE_PATHS):
        failures.append("Phase-2 retained source hash keys are incomplete")
    for key, relative in SOURCE_PATHS.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"missing Phase-2 retained source: {relative.as_posix()}")
            continue
        if source_hashes.get(key) != _sha256(path):
            failures.append(
                f"Phase-2 retained source hash mismatch: {relative.as_posix()}"
            )

    report_path = root / SOURCE_PATHS["phase1_exit_report"]
    if report_path.is_file():
        report = _load_json(report_path)
        if report.get("status") != "PASS":
            failures.append("Phase-1 retained report is not PASS")
        if report.get("total_discovery_families") != 2000:
            failures.append("Phase-1 retained family count is not 2,000")
        if report.get("confirmation", {}).get("status") != "RESERVED_NOT_GENERATED":
            failures.append("confirmation content is not safely reserved")
        if report.get("temporary_fixture_family_count") != 0:
            failures.append("Phase-1 retained corpus contains temporary fixtures")
    return failures


def _load_internal_harness(root: Path) -> ModuleType:
    path = root / "scripts/run-phase2-internal-check.py"
    spec = importlib.util.spec_from_file_location(
        "_nwm_phase2_internal_check",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the frozen Phase-2 harness")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_jsonl_gzip(
    path: Path,
    records: Iterable[dict[str, Any]],
) -> tuple[int, str]:
    rows = list(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw,
            mtime=0,
            compresslevel=9,
        ) as compressed:
            for record in rows:
                compressed.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    + b"\n"
                )
    return len(rows), _sha256(path)


def _git_head(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _uncommitted_phase2_inputs(root: Path) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--",
            *(relative.as_posix() for relative in PHASE2_INPUT_PATHS),
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ["cannot verify that Phase-2 retained inputs are committed to Git"]
    return [line for line in result.stdout.splitlines() if line]


def _logical_output_hashes(
    staging_data: Path,
    staging_artifacts: Path,
) -> dict[str, str]:
    values: dict[str, str] = {}
    for staging_root, logical_root in (
        (staging_data, PHASE2_DATA_RELATIVE_PATH),
        (staging_artifacts, PHASE2_ARTIFACT_RELATIVE_PATH),
    ):
        for path in sorted(staging_root.rglob("*")):
            if path.is_file() and path.name != "provenance_manifest.json":
                logical = logical_root / path.relative_to(staging_root)
                values[logical.as_posix()] = _sha256(path)
    return values


def _promote(
    staging_data: Path,
    staging_artifacts: Path,
    data_dir: Path,
    artifact_dir: Path,
) -> None:
    if data_dir.exists() or artifact_dir.exists():
        raise FileExistsError("refusing to overwrite existing Phase-2 retained outputs")
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


def run_phase2_retained(root: Path | None = None) -> dict[str, Any]:
    """Freeze the retained oracle harness, Static baseline, and arm exports."""

    root = (root or project_root()).resolve()
    failures = validate_phase2_retained_inputs(root)
    if failures:
        raise RuntimeError(
            "Phase-2 retained execution is blocked: " + "; ".join(failures)
        )
    config = _load_config(root)
    data_dir = root / PHASE2_DATA_RELATIVE_PATH
    artifact_dir = root / PHASE2_ARTIFACT_RELATIVE_PATH
    if data_dir.exists() or artifact_dir.exists():
        raise FileExistsError("Phase-2 retained outputs already exist")
    missing_phase2_inputs = [
        relative.as_posix()
        for relative in PHASE2_INPUT_PATHS
        if not (root / relative).is_file()
    ]
    if missing_phase2_inputs:
        raise RuntimeError(
            "Phase-2 retained execution inputs are missing: "
            + ", ".join(missing_phase2_inputs)
        )
    uncommitted_phase2_inputs = _uncommitted_phase2_inputs(root)
    if uncommitted_phase2_inputs:
        raise RuntimeError(
            "Phase-2 retained execution requires committed, byte-frozen inputs: "
            + "; ".join(uncommitted_phase2_inputs)
        )

    staging_root = root / ".tmp" / "phase2_retained" / uuid.uuid4().hex
    staging_data = staging_root / "data"
    staging_artifacts = staging_root / "artifacts"
    staging_data.mkdir(parents=True)
    staging_artifacts.mkdir(parents=True)

    families = _load_families(root / PHASE1_DATA_RELATIVE_PATH)
    if len(families) != 2000:
        raise RuntimeError("Phase-2 retained input does not contain 2,000 families")
    environment_counts = {
        environment: sum(
            family["environment"] == environment for family in families
        )
        for environment in ("game", "organization")
    }
    if environment_counts != {"game": 1000, "organization": 1000}:
        raise RuntimeError("Phase-2 retained environment counts are invalid")
    if len({family["scenario_id"] for family in families}) != 2000:
        raise RuntimeError("Phase-2 retained scenario IDs are not unique")

    bootstrap = config["bootstrap"]
    harness_module = _load_internal_harness(root)
    harness = harness_module.run_internal_check(
        root / PHASE1_DATA_RELATIVE_PATH,
        bootstrap_samples=int(bootstrap["samples"]),
        bootstrap_seed=int(bootstrap["seed"]),
    )
    harness["scope"] = "RETAINED_DISCOVERY_ORACLE_FIXTURE"
    harness["retained_input"] = True
    harness["scientific_model_result"] = False
    harness["confirmation_result"] = False
    harness["source_phase1_provenance_sha256"] = _sha256(
        root / SOURCE_PATHS["phase1_provenance_manifest"]
    )
    _write_json(staging_artifacts / "evaluation_harness.json", harness)

    baselines = run_smoke_baselines(
        root / PHASE1_DATA_RELATIVE_PATH,
        bootstrap_samples=int(bootstrap["samples"]),
        confidence_level=float(bootstrap["confidence_level"]),
        seed=int(bootstrap["seed"]),
    )
    baselines["status"] = "FROZEN_RETAINED_BASELINE"
    baselines["retained_or_confirmation_result"] = True
    baselines["retained_discovery_result"] = True
    baselines["confirmation_result"] = False
    baselines["data_scope"] = PHASE1_DATA_RELATIVE_PATH.as_posix()
    baselines["source_phase1_provenance_sha256"] = _sha256(
        root / SOURCE_PATHS["phase1_provenance_manifest"]
    )
    _write_json(staging_artifacts / "static_baselines.json", baselines)

    include_rollout = bool(config["exports"]["include_stored_rollout"])
    joint = build_joint_records(families, include_rollout=include_rollout)
    factual = build_factorized_factual_records(
        families,
        include_rollout=include_rollout,
    )
    normative = build_factorized_normative_records(families)
    visibility_failures = evaluator_visibility_failures(factual)
    exports: dict[str, Any] = {}
    for name, records in (
        ("joint_examples.jsonl.gz", joint),
        ("factorized_factual.jsonl.gz", factual),
        ("factorized_normative.jsonl.gz", normative),
    ):
        count, digest = _write_jsonl_gzip(staging_data / name, records)
        exports[name] = {"record_count": count, "sha256": digest}

    transfer = build_transfer_manifest(families)
    _write_json(staging_artifacts / "transfer_manifest.json", transfer)
    split_bindings = _split_bindings(families)
    overlap = _smoke_overlap(root, families)
    arm_manifest = {
        "status": (
            "PASS"
            if not visibility_failures and transfer["status"] == "READY"
            else "FAIL"
        ),
        "scope": "PHASE2_RETAINED_DISCOVERY_EXPORT",
        "run_kind": RUN_KIND,
        "family_count": len(families),
        "environment_counts": environment_counts,
        "files": exports,
        "joint_arm_views": ["joint_naive", "joint_consistency"],
        "factorized_pipeline": [
            "factorized_factual",
            "factorized_normative",
        ],
        "factorized_factual_evaluator_visibility_failure_count": len(
            visibility_failures
        ),
        "factorized_factual_evaluator_visibility_failure_examples": (
            visibility_failures[:20]
        ),
        "split_bindings": split_bindings,
        "smoke_overlap": overlap,
        "retained_discovery_is_independent_confirmation": False,
        "source_phase1_provenance_sha256": _sha256(
            root / SOURCE_PATHS["phase1_provenance_manifest"]
        ),
        "confirmation_status": "RESERVED_NOT_GENERATED",
        "h5_rollout_status": "UNIDENTIFIED",
        "note": (
            "The retained discovery corpus extends the externally reviewed smoke "
            "population and is not an independent confirmation population."
        ),
    }
    _write_json(staging_artifacts / "arm_data_manifest.json", arm_manifest)

    status_failures: list[str] = []
    if harness["status"] != "PASS":
        status_failures.append("retained oracle-fixture harness failed")
    if arm_manifest["status"] != "PASS":
        status_failures.append("retained arm export failed")
    if transfer["status"] != "READY":
        status_failures.append("retained transfer support is not identified")
    if any(
        item["exact_equal_overlap_count"] != 300
        or item["overlap_family_count"] != 300
        for item in overlap.values()
    ):
        status_failures.append("retained/smoke overlap does not match the disclosed 300 families")

    phase2_inputs = {
        relative.as_posix(): _sha256(root / relative)
        for relative in PHASE2_INPUT_PATHS
    }
    output_hashes = _logical_output_hashes(staging_data, staging_artifacts)
    provenance = {
        "status": "PASS" if not status_failures else "FAIL",
        "failures": status_failures,
        "run_kind": RUN_KIND,
        "git_head_before_execution": _git_head(root),
        "source_phase1": {
            key: {
                "path": relative.as_posix(),
                "sha256": _sha256(root / relative),
            }
            for key, relative in SOURCE_PATHS.items()
        },
        "phase2_inputs": phase2_inputs,
        "outputs": output_hashes,
        "split_bindings": split_bindings,
        "smoke_overlap": overlap,
        "bootstrap": bootstrap,
        "governance": {
            "retained_discovery_result": True,
            "confirmation_result": False,
            "confirmation_generation_authorized": False,
            "model_training_authorized": False,
            "h5_rollout_status": "UNIDENTIFIED",
        },
    }
    _write_json(staging_artifacts / "provenance_manifest.json", provenance)
    if status_failures:
        return {
            "status": "FAIL",
            "failures": status_failures,
            "staging_path": str(staging_root),
        }

    _promote(staging_data, staging_artifacts, data_dir, artifact_dir)
    try:
        staging_root.rmdir()
        staging_root.parent.rmdir()
    except OSError:
        pass
    return {
        "status": "PASS",
        "failures": [],
        "family_count": len(families),
        "environment_counts": environment_counts,
        "data_dir": PHASE2_DATA_RELATIVE_PATH.as_posix(),
        "artifact_dir": PHASE2_ARTIFACT_RELATIVE_PATH.as_posix(),
        "confirmation_status": "RESERVED_NOT_GENERATED",
        "h5_rollout_status": "UNIDENTIFIED",
    }


def verify_phase2_retained_artifacts(
    root: Path | None = None,
    *,
    require_outputs: bool = True,
) -> list[str]:
    """Verify every Phase-2 retained input and promoted output hash."""

    root = (root or project_root()).resolve()
    failures = validate_phase2_retained_inputs(root)
    data_dir = root / PHASE2_DATA_RELATIVE_PATH
    artifact_dir = root / PHASE2_ARTIFACT_RELATIVE_PATH
    if not data_dir.exists() and not artifact_dir.exists():
        if require_outputs:
            failures.append("Phase-2 retained outputs are missing")
        return failures
    if not data_dir.is_dir() or not artifact_dir.is_dir():
        failures.append("Phase-2 retained outputs are only partially promoted")
        return failures
    provenance_path = artifact_dir / "provenance_manifest.json"
    if not provenance_path.is_file():
        failures.append("Phase-2 retained provenance manifest is missing")
        return failures
    provenance = _load_json(provenance_path)
    if provenance.get("status") != "PASS":
        failures.append("Phase-2 retained provenance status is not PASS")
    for section in ("phase2_inputs", "outputs"):
        mapping = provenance.get(section)
        if not isinstance(mapping, dict):
            failures.append(f"Phase-2 retained {section} mapping is invalid")
            continue
        for relative, expected in mapping.items():
            path = root / relative
            if not path.is_file():
                failures.append(f"missing Phase-2 retained path: {relative}")
            elif _sha256(path) != expected:
                failures.append(f"Phase-2 retained hash mismatch: {relative}")
    source = provenance.get("source_phase1")
    if not isinstance(source, dict):
        failures.append("Phase-2 retained source binding is invalid")
    else:
        for item in source.values():
            if not isinstance(item, dict):
                failures.append("Phase-2 retained source binding entry is invalid")
                continue
            path = root / str(item.get("path", ""))
            if not path.is_file() or _sha256(path) != item.get("sha256"):
                failures.append(
                    f"Phase-2 retained source binding mismatch: {item.get('path')}"
                )
    arm_manifest_path = artifact_dir / "arm_data_manifest.json"
    harness_path = artifact_dir / "evaluation_harness.json"
    if arm_manifest_path.is_file():
        arm_manifest = _load_json(arm_manifest_path)
        if arm_manifest.get("status") != "PASS":
            failures.append("Phase-2 retained arm manifest is not PASS")
        if arm_manifest.get("family_count") != 2000:
            failures.append("Phase-2 retained arm manifest family count is not 2,000")
        if arm_manifest.get("confirmation_status") != "RESERVED_NOT_GENERATED":
            failures.append("Phase-2 arm export indicates confirmation generation")
    if harness_path.is_file():
        harness = _load_json(harness_path)
        if harness.get("status") != "PASS":
            failures.append("Phase-2 retained oracle fixture is not PASS")
        if harness.get("family_count") != 2000:
            failures.append("Phase-2 retained oracle fixture family count is not 2,000")
    return failures
