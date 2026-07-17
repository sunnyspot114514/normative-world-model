"""Verify a locally preserved V4 gateway result and its result lock."""

from __future__ import annotations

import json
from pathlib import Path

from normative_world_model.gateway_v4_result_lock import (
    verify_phase3_representation_gateway_v4_result,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures = verify_phase3_representation_gateway_v4_result(ROOT)
    print(
        json.dumps(
            {"status": "PASS" if not failures else "FAIL", "failures": failures},
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

