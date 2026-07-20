from __future__ import annotations

import json

from normative_world_model.phase5_synthetic_client_plan import (
    verify_phase5_synthetic_client_plan,
)


def main() -> None:
    print(
        json.dumps(
            verify_phase5_synthetic_client_plan(), indent=2, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
