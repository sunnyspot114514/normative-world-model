"""Export deterministic compressed smoke records for the three model arms."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from normative_world_model.model_arms import (
    build_factorized_factual_records,
    build_factorized_normative_records,
    build_joint_records,
    evaluator_visibility_failures,
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


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
    return len(rows), hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/generated/phase1_v3_smoke"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/generated/phase2_internal/arms"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/phase2_internal/arm_data_manifest.json"),
    )
    args = parser.parse_args()
    families = []
    for environment in ("game", "organization"):
        families.extend(_load_jsonl(args.data_dir / f"{environment}.jsonl"))

    joint = build_joint_records(families)
    factual = build_factorized_factual_records(families)
    normative = build_factorized_normative_records(families)
    visibility_failures = evaluator_visibility_failures(factual)
    datasets = {
        "joint_examples.jsonl.gz": joint,
        "factorized_factual.jsonl.gz": factual,
        "factorized_normative.jsonl.gz": normative,
    }
    files = {}
    for name, records in datasets.items():
        count, digest = _write_jsonl_gzip(args.output_dir / name, records)
        files[name] = {"record_count": count, "sha256": digest}
    manifest = {
        "status": "PASS" if not visibility_failures else "FAIL",
        "scope": "EXPLORATORY_V3_SMOKE_ONLY",
        "family_count": len(families),
        "files": files,
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
        "note": (
            "Gold event records are used only to train the normative component; "
            "evaluation must feed factorized factual predictions and recompute "
            "the policy result through the deterministic policy oracle."
        ),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if manifest["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
