"""Validate or execute the frozen Phase-2 retained-discovery stage."""

from __future__ import annotations

import argparse
import json

from normative_world_model.phase2_retained import (
    run_phase2_retained,
    validate_phase2_retained_inputs,
    verify_phase2_retained_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("validate-inputs", "run", "verify"),
        default="validate-inputs",
    )
    args = parser.parse_args()

    if args.mode == "validate-inputs":
        failures = validate_phase2_retained_inputs()
        result = {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "retained_execution_started": False,
        }
    elif args.mode == "verify":
        failures = verify_phase2_retained_artifacts(require_outputs=True)
        result = {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
        }
    else:
        try:
            result = run_phase2_retained()
        except (FileExistsError, RuntimeError) as error:
            result = {
                "status": "FAIL",
                "failures": [str(error)],
            }

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
