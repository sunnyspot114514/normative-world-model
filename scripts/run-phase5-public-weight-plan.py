from __future__ import annotations

import json

from normative_world_model.phase5_public_weight_plan import (
    default_public_weight_plan_path,
    run_public_weight_plan,
)


def main() -> int:
    result = run_public_weight_plan()
    print(
        json.dumps(
            {
                "status": result["status"],
                "artifact_sha256": result["artifact_sha256"],
                "output_path": str(default_public_weight_plan_path()),
                "totals": result["totals"],
                "authorization": result["authorization"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
