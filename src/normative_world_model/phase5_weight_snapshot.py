"""Exact post-download verifier for Phase-5 served checkpoint snapshots.

The verifier is read-only and has no downloader.  It combines the frozen public
weight plan with the frozen public-metadata manifest, then requires every served
snapshot byte to be an exact regular, single-link file inside its declared root.
"""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .phase5_public_metadata import _canonical_sha256, _load_inert_json
from .phase5_public_weight_plan import (
    WEIGHT_PLAN_FORMAT_VERSION,
    _artifact_sha256,
)

WEIGHT_SNAPSHOT_FORMAT_VERSION = "phase5-exact-weight-snapshot-v1"
STREAM_CHUNK_BYTES = 8 * 1024 * 1024


def _lower_sha256(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} is not a lowercase SHA-256")
    return value


def _safe_relative_path(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{label} is not a canonical relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or value != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"{label} is not a canonical relative path")
    return value


def _sha256_regular_file(path: Path, *, expected_size: int) -> str:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    digest = hashlib.sha256()
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size != expected_size
        ):
            raise ValueError(f"snapshot file descriptor contract differs: {path}")
        while chunk := os.read(descriptor, STREAM_CHUNK_BYTES):
            digest.update(chunk)
        after = os.fstat(descriptor)
        if (
            before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            raise ValueError(f"snapshot file changed while hashing: {path}")
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _verify_plan_documents(
    weight_plan: Mapping[str, Any],
    metadata_manifest: Mapping[str, Any],
    *,
    expected_weight_plan_sha256: str,
    expected_metadata_manifest_sha256: str,
) -> None:
    expected_weight = _lower_sha256(
        expected_weight_plan_sha256, label="external weight-plan binding"
    )
    without_hash = {key: value for key, value in weight_plan.items() if key != "artifact_sha256"}
    if (
        weight_plan.get("artifact_sha256") != expected_weight
        or _artifact_sha256(without_hash) != expected_weight
        or weight_plan.get("format_version") != WEIGHT_PLAN_FORMAT_VERSION
        or weight_plan.get("status") != "PASS_METADATA_ONLY_NO_WEIGHT_BYTES"
        or weight_plan.get("authorization")
        != {
            "model_download": False,
            "remote_fetch_performed": False,
            "weight_bytes_present": False,
        }
    ):
        raise ValueError("public weight plan differs from its closed external binding")
    expected_metadata = _lower_sha256(
        expected_metadata_manifest_sha256,
        label="external metadata-manifest binding",
    )
    metadata_without_hash = {
        key: value for key, value in metadata_manifest.items() if key != "manifest_sha256"
    }
    if (
        metadata_manifest.get("manifest_sha256") != expected_metadata
        or _canonical_sha256(metadata_without_hash) != expected_metadata
        or metadata_manifest.get("format_version") != "phase5-public-metadata-v1"
    ):
        raise ValueError("public metadata manifest differs from its external binding")


def _expected_checkpoint_files(
    weight_checkpoint: Mapping[str, Any],
    metadata_snapshot: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    if (
        weight_checkpoint.get("checkpoint") != metadata_snapshot.get("checkpoint")
        or weight_checkpoint.get("repo_id") != metadata_snapshot.get("repo_id")
        or weight_checkpoint.get("revision") != metadata_snapshot.get("revision")
    ):
        raise ValueError("weight and metadata checkpoint identities differ")
    result = {}
    weights = weight_checkpoint.get("weight_plan", {}).get("files")
    metadata = metadata_snapshot.get("files")
    if not isinstance(weights, list) or not isinstance(metadata, list):
        raise ValueError("publisher checkpoint file lists are malformed")
    for content_class, rows in (("weight", weights), ("metadata", metadata)):
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("publisher checkpoint file row is malformed")
            relative = _safe_relative_path(row.get("path"), label=f"{content_class} file path")
            if relative in result:
                raise ValueError(f"publisher checkpoint file is duplicated: {relative}")
            size = row.get("bytes")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise ValueError(f"publisher checkpoint size is invalid: {relative}")
            result[relative] = {
                "path": relative,
                "bytes": size,
                "sha256": _lower_sha256(
                    row.get("sha256"), label=f"publisher checkpoint digest/{relative}"
                ),
                "content_class": content_class,
            }
    return result


def _actual_regular_files(root: Path) -> dict[str, Path]:
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError(f"snapshot root is not an absolute regular directory: {root}")
    if getattr(root, "is_junction", lambda: False)():
        raise ValueError(f"snapshot root is a junction: {root}")
    for ancestor in root.parents:
        if ancestor.is_symlink() or getattr(ancestor, "is_junction", lambda: False)():
            raise ValueError(f"snapshot root has a linked ancestor: {ancestor}")
    resolved_root = root.resolve(strict=True)
    result = {}
    for item in sorted(root.rglob("*")):
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise ValueError(f"snapshot contains a link: {item}")
        resolved = item.resolve(strict=True)
        try:
            resolved.relative_to(resolved_root)
        except ValueError as error:
            raise ValueError(f"snapshot item escapes its root: {item}") from error
        if item.is_dir():
            continue
        if not item.is_file():
            raise ValueError(f"snapshot contains a non-regular item: {item}")
        if item.stat().st_nlink != 1:
            raise ValueError(f"snapshot file has multiple hard links: {item}")
        relative = item.relative_to(root).as_posix()
        _safe_relative_path(relative, label="actual snapshot path")
        result[relative] = item
    return result


def verify_downloaded_weight_snapshots(
    weight_plan: Mapping[str, Any],
    metadata_manifest: Mapping[str, Any],
    snapshot_roots: Mapping[str, Path],
    *,
    expected_weight_plan_sha256: str,
    expected_metadata_manifest_sha256: str,
) -> dict[str, Any]:
    """Hash and bind the exact two served snapshots after an authorized download."""

    _verify_plan_documents(
        weight_plan,
        metadata_manifest,
        expected_weight_plan_sha256=expected_weight_plan_sha256,
        expected_metadata_manifest_sha256=expected_metadata_manifest_sha256,
    )
    checkpoints = weight_plan.get("checkpoints")
    metadata_snapshots = metadata_manifest.get("snapshots")
    if (
        not isinstance(checkpoints, list)
        or not isinstance(metadata_snapshots, list)
        or len(checkpoints) != 2
        or len(metadata_snapshots) != 2
    ):
        raise ValueError("publisher checkpoint set is malformed")
    checkpoint_order = [row.get("checkpoint") for row in checkpoints]
    if checkpoint_order != ["agentworld", "base"]:
        raise ValueError("publisher checkpoint order differs")
    if not isinstance(snapshot_roots, Mapping) or set(snapshot_roots) != set(checkpoint_order):
        raise ValueError("downloaded snapshot root set differs")
    metadata_by_checkpoint = {
        row.get("checkpoint"): row for row in metadata_snapshots if isinstance(row, Mapping)
    }
    if set(metadata_by_checkpoint) != set(checkpoint_order):
        raise ValueError("metadata checkpoint set differs")

    snapshot_rows = []
    total_bytes = 0
    total_weight_bytes = 0
    for weight_checkpoint in checkpoints:
        checkpoint = weight_checkpoint["checkpoint"]
        expected = _expected_checkpoint_files(weight_checkpoint, metadata_by_checkpoint[checkpoint])
        root = snapshot_roots[checkpoint]
        if not isinstance(root, Path):
            raise ValueError(f"snapshot root must be a Path: {checkpoint}")
        actual = _actual_regular_files(root)
        if set(actual) != set(expected):
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            raise ValueError(
                f"snapshot exact file set differs: {checkpoint}; missing={missing}; extra={extra}"
            )
        files = []
        for relative in sorted(expected):
            contract = expected[relative]
            path = actual[relative]
            size = path.stat().st_size
            if size != contract["bytes"]:
                raise ValueError(f"snapshot file size differs: {checkpoint}/{relative}")
            digest = _sha256_regular_file(path, expected_size=contract["bytes"])
            if digest != contract["sha256"]:
                raise ValueError(f"snapshot file digest differs: {checkpoint}/{relative}")
            files.append(dict(contract))
            total_bytes += size
            if contract["content_class"] == "weight":
                total_weight_bytes += size
        if set(_actual_regular_files(root)) != set(expected):
            raise ValueError(f"snapshot file set changed while hashing: {checkpoint}")
        row = {
            "checkpoint": checkpoint,
            "repo_id": weight_checkpoint["repo_id"],
            "revision": weight_checkpoint["revision"],
            "snapshot_root": str(root),
            "files": files,
            "file_count": len(files),
            "total_bytes": sum(item["bytes"] for item in files),
            "weight_bytes": sum(
                item["bytes"] for item in files if item["content_class"] == "weight"
            ),
        }
        row["snapshot_manifest_sha256"] = _canonical_sha256(row)
        snapshot_rows.append(row)
    if total_weight_bytes != weight_plan.get("totals", {}).get("publisher_weight_bytes"):
        raise ValueError("verified snapshot weight-byte total differs from the plan")
    result = {
        "format_version": WEIGHT_SNAPSHOT_FORMAT_VERSION,
        "status": "PASS_EXACT_DOWNLOADED_SNAPSHOT_BYTES",
        "weight_plan_artifact_sha256": expected_weight_plan_sha256,
        "metadata_manifest_sha256": expected_metadata_manifest_sha256,
        "snapshots": snapshot_rows,
        "totals": {
            "checkpoint_count": len(snapshot_rows),
            "file_count": sum(row["file_count"] for row in snapshot_rows),
            "total_bytes": total_bytes,
            "weight_bytes": total_weight_bytes,
        },
    }
    result["snapshot_bundle_sha256"] = _canonical_sha256(result)
    return result


def load_inert_manifest(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"{label} is not a single-link regular file")
    value = _load_inert_json(path.read_bytes(), label=label)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value
