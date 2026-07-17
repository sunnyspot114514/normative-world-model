"""Verify the retained Phase-3 schema-gate result and local evidence."""

from __future__ import annotations

import json
from pathlib import Path

from normative_world_model.result_lock import verify_phase3_schema_gate_result

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures = verify_phase3_schema_gate_result(ROOT)
    result = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "confirmation_status": "RESERVED_NOT_GENERATED",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
