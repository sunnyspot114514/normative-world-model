"""Run cheap, smoke-only Phase-2 baselines."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from normative_world_model.baselines import run_smoke_baselines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/generated/phase1_v3_smoke"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/phase2_internal/baselines_v3_smoke.json"),
    )
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260916)
    args = parser.parse_args()
    report = run_smoke_baselines(
        args.data_dir,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
