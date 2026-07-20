from __future__ import annotations

import json

from normative_world_model.phase5_synthetic_client_plan import (
    default_phase5_synthetic_client_plan_path,
    run_phase5_synthetic_client_plan,
)


def main() -> None:
    result = run_phase5_synthetic_client_plan()
    print(
        json.dumps(
            {
                "status": result["status"],
                "client_plan_sha256": result["client_plan_sha256"],
                "request_count": result["request_count"],
                "output_path": str(
                    default_phase5_synthetic_client_plan_path(
                        runtime_plan_sha256=result["runtime_plan_binding"][
                            "runtime_plan_sha256"
                        ],
                        termination_plan_sha256=result["termination_plan_binding"][
                            "plan_sha256"
                        ],
                    )
                ),
                "http_execution": result["authorization"]["http_execution"],
                "server_process_execution": result["authorization"][
                    "server_process_execution"
                ],
                "scientific_execution": result["authorization"][
                    "scientific_execution"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
