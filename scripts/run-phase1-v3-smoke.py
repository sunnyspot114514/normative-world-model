"""Generate the preregistration-v3 internal smoke corpus."""

from __future__ import annotations

import argparse
import json

from normative_world_model.phase1_v3 import run_phase1_v3_smoke


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--families", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260716)
    args = parser.parse_args()
    report = run_phase1_v3_smoke(args.families, args.seed)
    print(
        json.dumps(
            {
                "status": report["status"],
                "run_kind": report["run_kind"],
                "families": report["total_discovery_families"],
                "failures": report["failures"],
                "retained_authorized": False,
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

