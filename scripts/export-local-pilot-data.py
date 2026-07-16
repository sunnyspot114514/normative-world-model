"""Export deterministic one-step views for the exploratory local pilot."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any, Iterable

from normative_world_model.model_arms import (
    build_factorized_factual_records,
    build_factorized_normative_records,
    build_joint_records,
    evaluator_visibility_failures,
)


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


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
        "--config",
        type=Path,
        default=Path("configs/local_pilot_qwen3_1_7b.toml"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("artifacts/phase3_internal/arm_data_manifest.json"),
    )
    args = parser.parse_args()
    config = _load_config(args.config)
    data_config = config["data"]
    source_dir = Path(data_config["source_phase1_dir"])
    output_dir = Path(data_config["output_dir"])
    families = []
    source_hashes = {}
    for environment in ("game", "organization"):
        path = source_dir / f"{environment}.jsonl"
        families.extend(_load_jsonl(path))
        source_hashes[path.as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    joint = build_joint_records(families, include_rollout=False)
    factual = build_factorized_factual_records(
        families,
        include_rollout=False,
    )
    normative = build_factorized_normative_records(families)
    visibility_failures = evaluator_visibility_failures(factual)
    datasets = {
        "joint_one_step.jsonl.gz": joint,
        "factorized_factual_one_step.jsonl.gz": factual,
        "factorized_normative.jsonl.gz": normative,
    }
    files = {}
    for name, records in datasets.items():
        count, digest = _write_jsonl_gzip(output_dir / name, records)
        files[name] = {"record_count": count, "sha256": digest}
    manifest = {
        "status": "PASS" if not visibility_failures else "FAIL",
        "scope": config["governance"]["scope"],
        "horizon_mode": data_config["horizon_mode"],
        "family_count": len(families),
        "source_hashes": source_hashes,
        "files": files,
        "factorized_factual_evaluator_visibility_failure_count": len(
            visibility_failures
        ),
        "factorized_factual_evaluator_visibility_failure_examples": (
            visibility_failures[:20]
        ),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
