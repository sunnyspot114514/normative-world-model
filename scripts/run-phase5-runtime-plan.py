from __future__ import annotations

import json

from normative_world_model.phase5_runtime_plan import (
    default_phase5_runtime_plan_path,
    run_phase5_runtime_plan,
)


def main() -> None:
    result = run_phase5_runtime_plan()
    print(
        json.dumps(
            {
                "status": result["status"],
                "runtime_plan_sha256": result["runtime_plan_sha256"],
                "checkpoint_count": len(result["launch_specs"]),
                "output_path": str(default_phase5_runtime_plan_path()),
                "model_download": result["authorization"]["model_download"],
                "server_rental": result["authorization"]["server_rental"],
                "http_execution": result["authorization"]["http_execution"],
                "gpu_execution": result["authorization"]["gpu_execution"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
