from __future__ import annotations

import json

from normative_world_model.phase5_termination_probe import (
    default_common_termination_probe_plan_path,
    run_common_termination_probe_plan,
)


def main() -> int:
    result = run_common_termination_probe_plan()
    print(
        json.dumps(
            {
                "status": result["status"],
                "plan_sha256": result["plan_sha256"],
                "case_count": len(result["cases"]),
                "public_prompt_token_count": result["public_prompt_token_count"],
                "http_execution": result["authorization"]["http_execution"],
                "output_path": str(default_common_termination_probe_plan_path()),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
