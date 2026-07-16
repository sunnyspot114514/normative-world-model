"""Run the externally accepted Phase-1 v3 retained discovery generator."""

from __future__ import annotations

import argparse
import json

from normative_world_model.retained_v3 import run_phase1_v3_retained


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("dry-run", "retained"),
        default="dry-run",
    )
    parser.add_argument("--families", type=int)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    report = run_phase1_v3_retained(
        mode=args.mode,
        families_per_environment=args.families,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "run_kind": report["run_kind"],
                "families": report["total_discovery_families"],
                "failures": report["failures"],
                "data_dir": report.get("data_dir"),
                "artifact_dir": report.get("artifact_dir"),
                "staging_path": report.get("staging_path"),
                "confirmation_status": report["confirmation"]["status"],
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
