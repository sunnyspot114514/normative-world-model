from __future__ import annotations

import json

from normative_world_model.phase5_termination_probe import (
    verify_common_termination_probe_plan,
)


def main() -> int:
    print(json.dumps(verify_common_termination_probe_plan(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
