"""Build and verify the metadata-only Phase-5 publisher weight plan.

This module reads only the already verified public metadata bundle.  It has no
network client and never downloads or opens model weight bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .phase5_preflight import STAGE2_CONFIG_SEMANTIC_SHA256, load_phase5_config
from .phase5_public_metadata import (
    FrozenPublicCheckpoint,
    _frozen_public_checkpoints,
    _load_inert_json,
    _verify_public_metadata_bundle,
    default_public_metadata_root,
)
from .phase5_serialization import resolve_publisher_weight_plan

WEIGHT_PLAN_FORMAT_VERSION = "phase5-public-weight-plan-v3"
WEIGHT_PLAN_MAX_BYTES = 2 * 1024 * 1024
IMPLEMENTATION_SOURCE_PATHS = (
    "src/normative_world_model/phase5_preflight.py",
    "src/normative_world_model/phase5_public_metadata.py",
    "src/normative_world_model/phase5_public_weight_plan.py",
    "src/normative_world_model/phase5_serialization.py",
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifact_sha256(value: Mapping[str, Any]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return _sha256_bytes((canonical + "\n").encode("utf-8"))


def _implementation_source_records() -> dict[str, dict[str, Any]]:
    project_root = Path(__file__).resolve().parents[2]
    records = {}
    for relative in IMPLEMENTATION_SOURCE_PATHS:
        body = (project_root / relative).read_bytes()
        records[relative] = {"bytes": len(body), "sha256": _sha256_bytes(body)}
    return records


def _build_public_weight_plan(
    metadata_root: Path,
    sources: Sequence[FrozenPublicCheckpoint],
) -> dict[str, Any]:
    verification = _verify_public_metadata_bundle(metadata_root, sources)
    if verification.get("status") != "PASS":
        raise ValueError("public metadata bundle verification did not pass")
    if any(path.suffix == ".safetensors" for path in metadata_root.rglob("*")):
        raise ValueError("public metadata bundle unexpectedly contains weight bytes")

    checkpoints = []
    for source in sources:
        checkpoint_root = metadata_root / source.checkpoint
        api_path = checkpoint_root / "publisher_api_response.json"
        index_path = checkpoint_root / "files" / "model.safetensors.index.json"
        api_bytes = api_path.read_bytes()
        index_bytes = index_path.read_bytes()
        api_document = _load_inert_json(
            api_bytes,
            label=f"{source.checkpoint}/publisher API response",
        )
        index_document = _load_inert_json(
            index_bytes,
            label=f"{source.checkpoint}/model index",
        )
        if not isinstance(api_document, Mapping) or not isinstance(
            api_document.get("siblings"), list
        ):
            raise ValueError(f"publisher API document is invalid: {source.checkpoint}")
        if api_document.get("sha") != source.revision:
            raise ValueError(f"publisher API revision mismatch: {source.checkpoint}")
        if not isinstance(index_document, Mapping):
            raise ValueError(f"model index is invalid: {source.checkpoint}")
        plan = resolve_publisher_weight_plan(
            index_document,
            api_document["siblings"],
        )
        if plan["unreferenced_weight_files"]:
            raise ValueError(
                f"publisher exposes unreferenced weight files: {source.checkpoint}"
            )
        if plan["index_declared_tensor_bytes"] is None:
            raise ValueError(f"model index lacks metadata.total_size: {source.checkpoint}")
        checkpoints.append(
            {
                "checkpoint": source.checkpoint,
                "repo_id": source.repo_id,
                "revision": source.revision,
                "publisher_api_response": {
                    "bytes": len(api_bytes),
                    "sha256": _sha256_bytes(api_bytes),
                },
                "model_safetensors_index": {
                    "bytes": len(index_bytes),
                    "sha256": _sha256_bytes(index_bytes),
                },
                "weight_plan": plan,
            }
        )

    result = {
        "format_version": WEIGHT_PLAN_FORMAT_VERSION,
        "status": "PASS_METADATA_ONLY_NO_WEIGHT_BYTES",
        "authorization": {
            "model_download": False,
            "remote_fetch_performed": False,
            "weight_bytes_present": False,
        },
        "stage2_config_semantic_sha256": STAGE2_CONFIG_SEMANTIC_SHA256,
        "implementation_sources": _implementation_source_records(),
        "metadata_bundle": {
            "directory_name": metadata_root.name,
            "verification": dict(verification),
        },
        "checkpoints": checkpoints,
        "totals": {
            "checkpoint_count": len(checkpoints),
            "weight_file_count": sum(
                row["weight_plan"]["weight_file_count"] for row in checkpoints
            ),
            "publisher_weight_bytes": sum(
                row["weight_plan"]["total_weight_bytes"] for row in checkpoints
            ),
            "index_declared_tensor_bytes": sum(
                row["weight_plan"]["index_declared_tensor_bytes"]
                for row in checkpoints
            ),
            "safetensors_container_overhead_bytes": sum(
                row["weight_plan"]["safetensors_container_overhead_bytes"]
                for row in checkpoints
            ),
        },
    }
    result["artifact_sha256"] = _artifact_sha256(result)
    return result


def default_public_weight_plan_path() -> Path:
    metadata_root = default_public_metadata_root()
    binding = metadata_root.name.removeprefix("v1-")
    return metadata_root.parents[1] / "phase5_public_weight_plan" / f"v3-{binding}.json"


def _write_weight_plan_once(path: Path, result: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite public weight plan: {path}")
    partial = path.with_name(path.name + ".part")
    data = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(data) > WEIGHT_PLAN_MAX_BYTES:
        raise ValueError("public weight plan exceeds its byte cap")
    try:
        with partial.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def run_public_weight_plan() -> dict[str, Any]:
    """Build the fixed metadata-only plan from the verified local snapshot."""

    metadata_root = default_public_metadata_root()
    sources = _frozen_public_checkpoints(load_phase5_config())
    result = _build_public_weight_plan(metadata_root, sources)
    _write_weight_plan_once(default_public_weight_plan_path(), result)
    return result


def _read_weight_plan(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("public weight plan is not a regular file")
    stat = path.stat()
    if stat.st_nlink != 1:
        raise ValueError("public weight plan has multiple hard links")
    if stat.st_size <= 0 or stat.st_size > WEIGHT_PLAN_MAX_BYTES:
        raise ValueError("public weight plan violates its byte cap")
    document = _load_inert_json(path.read_bytes(), label="public weight plan")
    if not isinstance(document, dict):
        raise ValueError("public weight plan must be an object")
    return document


def _verify_weight_plan_documents(
    stored: Mapping[str, Any],
    rebuilt: Mapping[str, Any],
) -> dict[str, Any]:
    without_hash = {key: value for key, value in stored.items() if key != "artifact_sha256"}
    if stored.get("artifact_sha256") != _artifact_sha256(without_hash):
        raise ValueError("public weight plan artifact hash is invalid")
    if stored != rebuilt:
        raise ValueError("stored public weight plan differs from an independent rebuild")
    return {
        "status": "PASS",
        "artifact_sha256": stored["artifact_sha256"],
        "checkpoint_count": stored["totals"]["checkpoint_count"],
        "weight_file_count": stored["totals"]["weight_file_count"],
        "publisher_weight_bytes": stored["totals"]["publisher_weight_bytes"],
        "model_download": stored["authorization"]["model_download"],
        "weight_bytes_present": stored["authorization"]["weight_bytes_present"],
    }


def verify_public_weight_plan() -> dict[str, Any]:
    """Rebuild the metadata plan independently and compare it exactly."""

    stored = _read_weight_plan(default_public_weight_plan_path())
    rebuilt = _build_public_weight_plan(
        default_public_metadata_root(),
        _frozen_public_checkpoints(load_phase5_config()),
    )
    return _verify_weight_plan_documents(stored, rebuilt)
