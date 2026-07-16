"""Read-only checks for the externally accepted Phase-1 v3 lifecycle."""

from __future__ import annotations

import argparse

from normative_world_model.generator import project_root
from normative_world_model.retained_v3 import (
    RETAINED_ARTIFACT_RELATIVE_PATH,
    RETAINED_DATA_RELATIVE_PATH,
    validate_v3_external_acceptance,
    verify_v3_retained_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-retained", action="store_true")
    args = parser.parse_args()

    failures = validate_v3_external_acceptance()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("V3 external acceptance and all bound smoke/source-lock bytes passed.")

    retained_failures = verify_v3_retained_artifacts(
        require_retained=args.require_retained
    )
    if retained_failures:
        for failure in retained_failures:
            print(f"FAIL: {failure}")
        return 1
    if args.require_retained:
        print("V3 retained discovery artifacts and provenance passed.")
    elif (
        (project_root() / RETAINED_DATA_RELATIVE_PATH).is_dir()
        and (project_root() / RETAINED_ARTIFACT_RELATIVE_PATH).is_dir()
    ):
        print("V3 retained discovery is present and valid.")
    else:
        print("V3 retained discovery is absent; external acceptance remains valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
