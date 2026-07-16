"""Build one deterministic, self-contained v3 external-review archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

FIXED_ZIP_TIME = (2026, 7, 16, 0, 0, 0)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _leaf_differences(
    left: Any,
    right: Any,
    path: tuple[str, ...] = (),
) -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        differences = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                differences.append(".".join((*path, key)))
            else:
                differences.extend(
                    _leaf_differences(
                        left[key],
                        right[key],
                        (*path, key),
                    )
                )
        return differences
    return [] if left == right else [".".join(path)]


def _row_index(
    record: dict[str, Any],
    *,
    line_number: int,
    raw_line: bytes,
) -> dict[str, Any]:
    source = record["source"]
    model_input = record["model_input"]
    computed_input_hash = _sha256(_canonical_bytes(model_input))
    rollout = record["rollout"]
    boundary = []
    for arm, result in (
        ("primary", record["primary"]),
        ("factual_twin", record["factual_twin"]["result"]),
        ("actor_value_twin", record["actor_value_twin"]["result"]),
        ("policy_twin", record["policy_twin"]["result"]),
    ):
        for profile_id, evaluation in result["evaluations"].items():
            if evaluation["score_margin_to_boundary"] == 0.0:
                boundary.append(
                    {
                        "arm": arm,
                        "profile_id": profile_id,
                        "decision": evaluation["decision"],
                        "score": evaluation["score"],
                    }
                )
    twin_paths = {
        name: _leaf_differences(source, record[name]["source"])
        for name in ("factual_twin", "actor_value_twin", "policy_twin")
    }
    return {
        "environment": record["environment"],
        "line_number": line_number,
        "scenario_id": record["scenario_id"],
        "split": record["split"],
        "action_family": record["source"]["action"]["family"],
        "raw_line_sha256": _sha256(raw_line),
        "stored_model_input_sha256": record["model_input_sha256"],
        "computed_model_input_sha256": computed_input_hash,
        "model_input_hash_matches": (
            computed_input_hash == record["model_input_sha256"]
        ),
        "twin_source_difference_paths": twin_paths,
        "physical_relations": {
            "factual_changed": (
                record["factual_twin"]["result"]["physical_delta"]
                != record["primary"]["physical_delta"]
            ),
            "actor_changed": (
                record["actor_value_twin"]["result"]["physical_delta"]
                != record["primary"]["physical_delta"]
            ),
            "policy_preserved": (
                record["policy_twin"]["result"]["physical_delta"]
                == record["primary"]["physical_delta"]
            ),
        },
        "rollout_chain_valid": (
            len(rollout) == 3
            and record["primary"]["next_state"] == rollout[0]["next_state"]
            and all(
                left["next_state"] == right["pre_state"]
                for left, right in zip(rollout, rollout[1:], strict=False)
            )
        ),
        "exact_boundary_evaluations": boundary,
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_deterministic_zip(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(relative, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def build_bundle(root: Path) -> dict[str, Any]:
    root = root.resolve()
    data_dir = (root / "data" / "generated" / "phase1_v3_smoke").resolve()
    artifact_dir = (root / "artifacts" / "phase1_v3_smoke").resolve()
    output_dir = (artifact_dir / "external_audit_bundle_v3").resolve()
    archive_path = (artifact_dir / "external_audit_bundle_v3.zip").resolve()
    for path in (data_dir, artifact_dir, output_dir, archive_path):
        path.relative_to(root)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir()

    sample_report = json.loads(
        (artifact_dir / "deterministic_review_sample.json").read_text(
            encoding="utf-8"
        )
    )
    sample_ids = {
        row["scenario_id"]
        for row in sample_report["rows"]
    }
    records: dict[str, dict[str, Any]] = {}
    indices = []
    corpus_hashes = {}
    for environment in ("game", "organization"):
        source_path = data_dir / f"{environment}.jsonl"
        destination = raw_dir / source_path.name
        shutil.copyfile(source_path, destination)
        corpus_hashes[
            source_path.relative_to(root).as_posix()
        ] = _sha256(source_path.read_bytes())
        with source_path.open("rb") as handle:
            for line_number, raw_with_newline in enumerate(handle, start=1):
                raw_line = raw_with_newline.rstrip(b"\r\n")
                if not raw_line:
                    continue
                record = json.loads(raw_line)
                records[record["scenario_id"]] = record
                indices.append(
                    _row_index(
                        record,
                        line_number=line_number,
                        raw_line=raw_line,
                    )
                )

    (output_dir / "row_audit_index.jsonl").write_text(
        "".join(
            json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for item in indices
        ),
        encoding="utf-8",
    )
    (output_dir / "deterministic_sample_full_rows.jsonl").write_text(
        "".join(
            json.dumps(
                records[scenario_id],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for scenario_id in sorted(sample_ids)
        ),
        encoding="utf-8",
    )

    for name in (
        "phase1_exit_report.json",
        "provenance_manifest.json",
        "independent_internal_audit.json",
        "deterministic_review_sample.json",
        "DATASET_CARD.md",
        "uncertainty_reachability.md",
    ):
        shutil.copyfile(artifact_dir / name, output_dir / name)
    shutil.copyfile(
        data_dir / "confirmation_reservation.json",
        output_dir / "confirmation_reservation.json",
    )
    contracts = output_dir / "contracts"
    contracts.mkdir()
    for relative in (
        "PREREGISTRATION_V3.md",
        "configs/preregistration_v3.toml",
        "docs/NORMATIVE_PREDICATE_CONTRACT.md",
        "docs/EVALUATOR_PROFILES.md",
        "docs/LEAKAGE_AUDIT_SPEC.md",
        "docs/METRIC_COMPARATOR_V2_1.md",
        "docs/INTERNAL_REVIEW_PROTOCOL.md",
        "docs/PHASE1_V2_INTERNAL_REVIEW.md",
        "docs/PHASE1_V3_REVISION0_INTERNAL_REVIEW.md",
        "docs/PHASE1_V3_INTERNAL_SMOKE.md",
        "docs/EXTERNAL_SMOKE_ACCEPTANCE_V3.md",
    ):
        source = root / relative
        shutil.copyfile(source, contracts / source.name)

    manifest_hash = _sha256(
        (artifact_dir / "provenance_manifest.json").read_bytes()
    )
    _write_json(
        output_dir / "EXTERNAL_AUDIT_ACCEPTED.template.json",
        {
            "status": "REVIEW_REQUIRED",
            "unconditional": False,
            "preregistration_version": 3,
            "generator_revision": 1,
            "run_kind": "v3_internal_smoke",
            "reviewer": "",
            "reviewed_at": "",
            "provenance_manifest_sha256": manifest_hash,
            "corpus_sha256": corpus_hashes,
            "blocking_findings": [],
            "notes": "",
        },
    )
    summary = {
        "status": "READY_FOR_EXTERNAL_REVIEW",
        "full_corpus_included": True,
        "full_corpus_row_count": len(indices),
        "deterministic_sample_row_count": len(sample_ids),
        "corpus_sha256": corpus_hashes,
        "provenance_manifest_sha256": manifest_hash,
        "index_checks": {
            "model_input_hash_mismatch_count": sum(
                not item["model_input_hash_matches"] for item in indices
            ),
            "invalid_rollout_chain_count": sum(
                not item["rollout_chain_valid"] for item in indices
            ),
            "factual_physical_unchanged_count": sum(
                not item["physical_relations"]["factual_changed"]
                for item in indices
            ),
            "actor_physical_unchanged_count": sum(
                not item["physical_relations"]["actor_changed"]
                for item in indices
            ),
            "policy_physical_changed_count": sum(
                not item["physical_relations"]["policy_preserved"]
                for item in indices
            ),
            "exact_boundary_row_count": sum(
                bool(item["exact_boundary_evaluations"]) for item in indices
            ),
        },
    }
    _write_json(output_dir / "audit_bundle_summary.json", summary)
    (output_dir / "AUDIT_README.md").write_text(
        """# V3 revision-1 external-audit bundle

Status: **READY FOR EXTERNAL REVIEW; NOT ACCEPTED**

This archive includes both complete raw JSONL files, their row-level hash/index view, the fixed
36-row readable sample as full records, native and independent reports, the confirmation
reservation, and the exact governing contracts.

Review the raw rows and contracts, then compare every accepted hash with
`EXTERNAL_AUDIT_ACCEPTED.template.json`. Internal reports are evidence to inspect, not external
acceptance. Do not generate or inspect confirmation content.
""",
        encoding="utf-8",
    )
    bundle_manifest = {
        path.relative_to(output_dir).as_posix(): _sha256(path.read_bytes())
        for path in sorted(item for item in output_dir.rglob("*") if item.is_file())
        if path.name != "bundle_manifest.json"
    }
    _write_json(
        output_dir / "bundle_manifest.json",
        {"files": bundle_manifest, "summary": summary},
    )
    _write_deterministic_zip(output_dir, archive_path)
    summary["archive_path"] = archive_path.relative_to(root).as_posix()
    summary["archive_sha256"] = _sha256(archive_path.read_bytes())
    summary["archive_size_bytes"] = archive_path.stat().st_size
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    summary = build_bundle(args.project_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
