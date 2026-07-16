"""Download and hash the exact local-pilot checkpoint revision."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, snapshot_download
from transformers import AutoConfig, AutoTokenizer


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


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
        default=Path("artifacts/phase3_internal/model_snapshot_manifest.json"),
    )
    args = parser.parse_args()
    config = _load_config(args.config)
    model_config = config["model"]
    model_id = model_config["model_id"]
    revision = model_config["revision"]
    local_dir = Path(model_config["local_dir"]).resolve()
    info = HfApi().model_info(model_id, revision=revision)
    if info.sha != revision:
        raise SystemExit(
            f"Hub revision mismatch: requested {revision}, resolved {info.sha}"
        )
    snapshot_download(
        repo_id=model_id,
        revision=revision,
        local_dir=local_dir,
    )
    hf_config = AutoConfig.from_pretrained(
        local_dir,
        local_files_only=True,
        trust_remote_code=False,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        local_dir,
        local_files_only=True,
        trust_remote_code=False,
    )
    files = {}
    for path in sorted(local_dir.rglob("*")):
        if not path.is_file() or ".cache" in path.relative_to(local_dir).parts:
            continue
        relative = path.relative_to(local_dir).as_posix()
        files[relative] = {
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    manifest = {
        "status": "PASS",
        "scope": config["governance"]["scope"],
        "model_id": model_id,
        "requested_revision": revision,
        "resolved_revision": info.sha,
        "license": model_config["license"],
        "local_dir": str(local_dir),
        "model_type": hf_config.model_type,
        "architectures": list(hf_config.architectures or []),
        "vocabulary_size": len(tokenizer),
        "files": files,
        "total_snapshot_bytes": sum(item["bytes"] for item in files.values()),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {
            name: version(name)
            for name in (
                "accelerate",
                "hf-xet",
                "huggingface-hub",
                "peft",
                "safetensors",
                "torch",
                "transformers",
            )
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
