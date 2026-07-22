from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from normative_world_model.phase5_public_metadata import _canonical_sha256, _load_inert_json
from normative_world_model.phase5_runtime_plan import _read_runtime_plan
from normative_world_model.phase5_synthetic_client_plan import _read_client_plan
from normative_world_model.phase5_synthetic_runner import (
    SyntheticRuntimeSpec,
    runtime_bindings_from_specs,
)
from normative_world_model.phase5_termination_probe import _read_plan


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINTS = {
    "agentworld": {
        "repo_id": "Qwen/Qwen-AgentWorld-35B-A3B",
        "revision": "60d2b0434a53d2e62a7c00a489586815d94ebffb",
    },
    "base": {
        "repo_id": "Qwen/Qwen3.5-35B-A3B-Base",
        "revision": "0f0813072d2358973511097385626f21fcb6d422",
    },
}
WEIGHT_PLAN_ARTIFACT_SHA256 = "ee5eaa6d9fb3b9da9ede408743dacad0ed6c9bf6e4495307a662deff23ab6c8c"
SOURCE_POSTVERIFY_SHA256 = "52c7fffb1ff8209b8b86cdfa675bf09cd816e5dd9439bedc641bd4f0f0906061"
CLONE_POSTVERIFY_SHA256 = "8b637956cfb11758da3d822d916c4ca8b2e0680714396ec3b7a6763764fb358d"


def _json(path: Path, *, label: str) -> dict[str, Any]:
    value = _load_inert_json(path.read_bytes(), label=label)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _snapshot_manifest(postverify: dict[str, Any], checkpoint: str) -> dict[str, Any]:
    identity = CHECKPOINTS[checkpoint]
    prefix = f"{checkpoint}/{identity['revision']}/"
    rows = []
    for content_class, source_rows in (
        ("weight", postverify["weights"]),
        ("metadata", postverify["metadata"]),
    ):
        for source in source_rows:
            relative = source["relative"]
            if not relative.startswith(prefix):
                continue
            rows.append(
                {
                    "path": relative[len(prefix) :],
                    "bytes": source["bytes"],
                    "sha256": source["sha256"],
                    "content_class": content_class,
                }
            )
    rows.sort(key=lambda row: row["path"])
    if not rows:
        raise ValueError(f"postverify has no rows for {checkpoint}")
    manifest = {
        "checkpoint": checkpoint,
        "repo_id": identity["repo_id"],
        "revision": identity["revision"],
        "snapshot_root": f"/root/autodl-tmp/models/phase5/{checkpoint}/{identity['revision']}",
        "files": rows,
        "file_count": len(rows),
        "total_bytes": sum(row["bytes"] for row in rows),
        "weight_bytes": sum(
            row["bytes"] for row in rows if row["content_class"] == "weight"
        ),
    }
    manifest["snapshot_manifest_sha256"] = _canonical_sha256(manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--postverify",
        type=Path,
        default=ROOT / ".tmp" / "phase5_snapshot_postverify_result.json",
    )
    parser.add_argument(
        "--clone-postverify",
        type=Path,
        default=ROOT / ".tmp" / "phase5_clone_postverify_result.json",
    )
    parser.add_argument(
        "--environment",
        type=Path,
        default=ROOT / "configs" / "phase5_lock_a_remote_environment_20260722.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "configs" / "phase5_lock_a_runtime_bundle_20260722.json",
    )
    args = parser.parse_args()

    postverify = _json(args.postverify, label="source snapshot postverify")
    clone_postverify = _json(args.clone_postverify, label="clone postverify")
    environment_manifest = _json(args.environment, label="remote environment manifest")
    if (
        postverify.get("result_sha256") != SOURCE_POSTVERIFY_SHA256
        or clone_postverify.get("result_sha256") != CLONE_POSTVERIFY_SHA256
        or environment_manifest.get("manifest_sha256")
        != _canonical_sha256(
            {key: value for key, value in environment_manifest.items() if key != "manifest_sha256"}
        )
    ):
        raise ValueError("source evidence self-hash differs")

    client = _read_client_plan(
        ROOT / ".cache" / "phase5_synthetic_client_plan" / "v10-b2887ba90d81-b752a05215d7.json"
    )
    termination = _read_plan(
        ROOT / ".cache" / "phase5_common_termination_probe_plan" / "v2-1a8cdbf5f807.json"
    )
    runtime = _read_runtime_plan(
        ROOT / ".cache" / "phase5_runtime_plan" / "v2-2a23d1973113-1a8cdbf5f807.json"
    )
    launch_by_checkpoint = {row["checkpoint"]: row for row in runtime["launch_specs"]}
    effective_environment = {
        **runtime["environment_contract"]["required_environment"],
        "PATH": (
            "/root/autodl-tmp/phase5-preflight/bin:/usr/local/sbin:/usr/local/bin:"
            "/usr/sbin:/usr/bin:/sbin:/bin"
        ),
        "HOME": "/root",
        "TMPDIR": "/root/autodl-tmp/.tmp",
        "XDG_CACHE_HOME": "/root/autodl-tmp/.cache",
        "HF_HOME": "/root/autodl-tmp/.cache/huggingface",
        "TORCHINDUCTOR_CACHE_DIR": "/root/autodl-tmp/.cache/torchinductor",
        "TRITON_CACHE_DIR": "/root/autodl-tmp/.cache/triton",
    }
    specs = {}
    for checkpoint in ("agentworld", "base"):
        snapshot = _snapshot_manifest(postverify, checkpoint)
        launch = launch_by_checkpoint[checkpoint]
        argv = [environment_manifest["runtime_executable"], *launch["argv"]]
        argv[2] = snapshot["snapshot_root"]
        specs[checkpoint] = SyntheticRuntimeSpec(
            checkpoint=checkpoint,
            snapshot_manifest=snapshot,
            effective_environment=effective_environment,
            argv=tuple(argv),
        )
    bindings = runtime_bindings_from_specs(specs)
    bundle = {
        "format_version": "phase5-lock-a-runtime-bundle-v1",
        "status": "LOCK_A_RUNTIME_BUNDLE_PUBLIC_SYNTHETIC_ONLY",
        "client_plan_sha256": client["client_plan_sha256"],
        "termination_plan_sha256": termination["plan_sha256"],
        "runtime_plan_sha256": runtime["runtime_plan_sha256"],
        "weight_download_plan_sha256": WEIGHT_PLAN_ARTIFACT_SHA256,
        "source_postverify_result_sha256": SOURCE_POSTVERIFY_SHA256,
        "clone_postverify_result_sha256": CLONE_POSTVERIFY_SHA256,
        "remote_environment_manifest_sha256": environment_manifest["manifest_sha256"],
        "runtime_specs": {
            checkpoint: {
                "snapshot_manifest": dict(specs[checkpoint].snapshot_manifest),
                "effective_environment": dict(specs[checkpoint].effective_environment),
                "argv": list(specs[checkpoint].argv),
            }
            for checkpoint in ("agentworld", "base")
        },
        "runtime_bindings_sha256": _canonical_sha256(bindings),
    }
    bundle["bundle_sha256"] = _canonical_sha256(bundle)
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite runtime bundle: {args.output}")
    args.output.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: bundle[key] for key in (
        "bundle_sha256", "client_plan_sha256", "runtime_bindings_sha256"
    )}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
