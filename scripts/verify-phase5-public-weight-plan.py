from __future__ import annotations

import json

from normative_world_model.phase5_public_weight_plan import verify_public_weight_plan


def main() -> int:
    print(json.dumps(verify_public_weight_plan(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
