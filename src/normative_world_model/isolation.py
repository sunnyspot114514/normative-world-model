"""Audit that writable project paths and the active interpreter stay inside the root."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping

PATH_ENV_VARS = {
    "NWM_PROJECT_ROOT": ".",
    "UV_PROJECT_ENVIRONMENT": ".venv",
    "UV_CACHE_DIR": ".cache/uv",
    "PIP_CACHE_DIR": ".cache/pip",
    "HF_HOME": ".cache/huggingface",
    "HF_HUB_CACHE": ".cache/huggingface/hub",
    "HF_DATASETS_CACHE": ".cache/huggingface/datasets",
    "TORCH_HOME": ".cache/torch",
    "XDG_CACHE_HOME": ".cache",
    "WANDB_DIR": "runs/wandb",
    "WANDB_CACHE_DIR": ".cache/wandb",
    "WANDB_CONFIG_DIR": ".cache/wandb-config",
    "TEMP": ".tmp",
    "TMP": ".tmp",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def expected_paths(root: Path | None = None) -> dict[str, Path]:
    base = (root or project_root()).resolve()
    return {key: (base / relative).resolve() for key, relative in PATH_ENV_VARS.items()}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def audit_environment(environ: Mapping[str, str] | None = None) -> list[str]:
    env = environ or os.environ
    root = project_root()
    failures: list[str] = []

    for key, expected in expected_paths(root).items():
        raw = env.get(key)
        if not raw:
            failures.append(f"{key} is not set")
            continue
        actual = Path(raw).resolve()
        if actual != expected:
            failures.append(f"{key} points to {actual}, expected {expected}")
        if not _inside(actual, root):
            failures.append(f"{key} escapes the project root: {actual}")

    venv = (root / ".venv").resolve()
    if not _inside(Path(sys.prefix), venv):
        failures.append(f"active interpreter is outside .venv: {sys.prefix}")
    if env.get("PYTHONNOUSERSITE") != "1":
        failures.append("PYTHONNOUSERSITE must equal 1")

    return failures

