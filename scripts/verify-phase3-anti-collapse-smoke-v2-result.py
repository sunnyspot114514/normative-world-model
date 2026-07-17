"""Verify the preserved Phase-3 anti-collapse smoke v2 result."""

from __future__ import annotations

import json
from pathlib import Path

from normative_world_model.smoke_v2_result_lock import (
    verify_phase3_anti_collapse_smoke_v2_result,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures = verify_phase3_anti_collapse_smoke_v2_result(ROOT)
    result = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "v1_status": "BLOCKED",
        "v2_status": "BLOCKED",
        "formal_arm_comparison_started": False,
        "confirmation_status": "RESERVED_NOT_GENERATED",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
