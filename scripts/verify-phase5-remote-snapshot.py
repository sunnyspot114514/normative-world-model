#!/usr/bin/env python3
"""Independent post-download verifier for the frozen Phase-5 public snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

EXPECTED_WEIGHT_COUNT = 35
EXPECTED_WEIGHT_BYTES = 141_225_192_536
EXPECTED_METADATA_COUNT = 16
EXPECTED_METADATA_BYTES = 46_074_242
EXPECTED_METADATA_MANIFEST_FILE_SHA256 = (
    "3a590f42a4e2a5cc128acc92b9f6f084423dd53110267e720574ee0c69a9867a"
)
EXPECTED_METADATA_MANIFEST_SHA256 = (
    "a8b8544ee8162e1634097b0d7194197d6c03244c98dcf134e818f59b9d872b3a"
)
EXPECTED_CHECKPOINTS = {
    "agentworld": {
        "repo_id": "Qwen/Qwen-AgentWorld-35B-A3B",
        "revision": "60d2b0434a53d2e62a7c00a489586815d94ebffb",
    },
    "base": {
        "repo_id": "Qwen/Qwen3.5-35B-A3B-Base",
        "revision": "0f0813072d2358973511097385626f21fcb6d422",
    },
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256((payload + "\n").encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _regular_unlinked(path: Path) -> os.stat_result:
    observed = path.lstat()
    if not stat.S_ISREG(observed.st_mode) or path.is_symlink() or observed.st_nlink != 1:
        raise ValueError(f"not a regular single-link file: {path}")
    return observed


def _safe_relative(root: Path, relative: Path) -> Path:
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes target root: {relative}")
    return target


def _atomic_json(path: Path, value: Any) -> None:
    partial = path.with_suffix(path.suffix + ".part")
    partial.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(partial, path)


def verify(
    *,
    weights_tsv: Path,
    metadata_manifest_path: Path,
    metadata_evidence_root: Path,
    target_root: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        weights_tsv.read_text(encoding="utf-8").splitlines(), start=1
    ):
        fields = line.split("\t")
        if len(fields) != 6:
            raise ValueError(f"weight manifest row {line_number} has the wrong field count")
        checkpoint, repo_id, revision, relative, byte_text, expected_sha256 = fields
        identity = EXPECTED_CHECKPOINTS.get(checkpoint)
        if identity != {"repo_id": repo_id, "revision": revision}:
            raise ValueError(f"weight manifest identity differs at row {line_number}")
        relative_path = Path(checkpoint) / revision / relative
        if Path(relative).name != relative or not relative.endswith(".safetensors"):
            raise ValueError(f"unsafe weight path at row {line_number}")
        rows.append(
            {
                "checkpoint": checkpoint,
                "relative": relative_path.as_posix(),
                "bytes": int(byte_text),
                "sha256": expected_sha256,
            }
        )
    if (
        len(rows) != EXPECTED_WEIGHT_COUNT
        or len({row["relative"] for row in rows}) != EXPECTED_WEIGHT_COUNT
        or sum(row["bytes"] for row in rows) != EXPECTED_WEIGHT_BYTES
    ):
        raise ValueError("weight manifest count, uniqueness, or total differs")

    expected_weight_paths = {row["relative"] for row in rows}
    actual_weight_paths = {
        path.relative_to(target_root).as_posix()
        for path in target_root.rglob("*.safetensors")
        if path.is_file()
    }
    if actual_weight_paths != expected_weight_paths:
        raise ValueError("weight file inventory differs from the frozen manifest")

    verified_weights: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        path = _safe_relative(target_root, Path(row["relative"]))
        observed = _regular_unlinked(path)
        observed_sha256 = _sha256_file(path)
        if observed.st_size != row["bytes"] or observed_sha256 != row["sha256"]:
            raise ValueError(f"weight bytes differ: {row['relative']}")
        verified_weights.append(
            {
                "relative": row["relative"],
                "bytes": observed.st_size,
                "sha256": observed_sha256,
            }
        )
        print(f"weight_verified={index}/{EXPECTED_WEIGHT_COUNT} path={row['relative']}", flush=True)

    _regular_unlinked(metadata_manifest_path)
    if _sha256_file(metadata_manifest_path) != EXPECTED_METADATA_MANIFEST_FILE_SHA256:
        raise ValueError("public metadata manifest file hash differs")
    metadata_manifest = _load_json(metadata_manifest_path)
    manifest_without_hash = {
        key: value for key, value in metadata_manifest.items() if key != "manifest_sha256"
    }
    if (
        metadata_manifest.get("manifest_sha256") != EXPECTED_METADATA_MANIFEST_SHA256
        or _canonical_sha256(manifest_without_hash) != EXPECTED_METADATA_MANIFEST_SHA256
    ):
        raise ValueError("public metadata manifest semantic hash differs")
    snapshots = metadata_manifest.get("snapshots")
    if not isinstance(snapshots, list) or len(snapshots) != 2:
        raise ValueError("public metadata snapshot count differs")

    expected_metadata_paths: set[str] = set()
    verified_metadata: list[dict[str, Any]] = []
    for snapshot in snapshots:
        checkpoint = snapshot.get("checkpoint")
        identity = EXPECTED_CHECKPOINTS.get(checkpoint)
        if identity != {
            "repo_id": snapshot.get("repo_id"),
            "revision": snapshot.get("revision"),
        }:
            raise ValueError(f"public metadata identity differs: {checkpoint}")
        snapshot_manifest_path = metadata_evidence_root / checkpoint / "snapshot_manifest.json"
        publisher_response_path = (
            metadata_evidence_root / checkpoint / "publisher_api_response.json"
        )
        _regular_unlinked(snapshot_manifest_path)
        _regular_unlinked(publisher_response_path)
        if _load_json(snapshot_manifest_path) != snapshot:
            raise ValueError(f"snapshot manifest differs from bundle: {checkpoint}")
        snapshot_without_hash = {
            key: value for key, value in snapshot.items() if key != "snapshot_manifest_sha256"
        }
        if _canonical_sha256(snapshot_without_hash) != snapshot.get("snapshot_manifest_sha256"):
            raise ValueError(f"snapshot semantic hash differs: {checkpoint}")
        if _sha256_file(publisher_response_path) != snapshot.get("api_response_sha256"):
            raise ValueError(f"publisher API response differs: {checkpoint}")
        files = snapshot.get("files")
        if not isinstance(files, list) or len(files) != snapshot.get("file_count"):
            raise ValueError(f"metadata file count differs: {checkpoint}")
        for file_record in files:
            relative = Path(checkpoint) / snapshot["revision"] / file_record["path"]
            relative_text = relative.as_posix()
            if relative_text in expected_metadata_paths:
                raise ValueError(f"duplicate metadata path: {relative_text}")
            expected_metadata_paths.add(relative_text)
            path = _safe_relative(target_root, relative)
            observed = _regular_unlinked(path)
            observed_sha256 = _sha256_file(path)
            if (
                observed.st_size != file_record.get("bytes")
                or observed_sha256 != file_record.get("sha256")
            ):
                raise ValueError(f"public metadata bytes differ: {relative_text}")
            verified_metadata.append(
                {
                    "relative": relative_text,
                    "bytes": observed.st_size,
                    "sha256": observed_sha256,
                }
            )

    if (
        len(verified_metadata) != EXPECTED_METADATA_COUNT
        or sum(row["bytes"] for row in verified_metadata) != EXPECTED_METADATA_BYTES
    ):
        raise ValueError("public metadata count or byte total differs")
    expected_all_paths = expected_weight_paths | expected_metadata_paths
    actual_all_paths = {
        path.relative_to(target_root).as_posix()
        for path in target_root.rglob("*")
        if path.is_file()
    }
    if actual_all_paths != expected_all_paths:
        raise ValueError("target snapshot contains missing or extra files")
    result = {
        "format_version": "phase5-independent-snapshot-postverify-v1",
        "status": "PASS",
        "weight_file_count": len(verified_weights),
        "weight_bytes": sum(row["bytes"] for row in verified_weights),
        "metadata_file_count": len(verified_metadata),
        "metadata_bytes": sum(row["bytes"] for row in verified_metadata),
        "weights": verified_weights,
        "metadata": verified_metadata,
    }
    result["result_sha256"] = _canonical_sha256(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights-tsv", type=Path, required=True)
    parser.add_argument("--metadata-manifest", type=Path, required=True)
    parser.add_argument("--metadata-evidence-root", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.output_root.exists():
        raise FileExistsError("post-verification output root already exists")
    args.output_root.mkdir(parents=True)
    try:
        result = verify(
            weights_tsv=args.weights_tsv,
            metadata_manifest_path=args.metadata_manifest,
            metadata_evidence_root=args.metadata_evidence_root,
            target_root=args.target_root,
        )
    except Exception as error:
        _atomic_json(
            args.output_root / "FAILED.json",
            {"status": "FAILED", "error_type": type(error).__name__, "message": str(error)},
        )
        raise
    _atomic_json(args.output_root / "result.json", result)
    (args.output_root / "PASS").write_text(
        f"result_sha256={result['result_sha256']}\n", encoding="utf-8"
    )
    print(f"postverify_status=PASS result_sha256={result['result_sha256']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
