"""Small command-line entry point for project diagnostics."""

from __future__ import annotations

import argparse

from .isolation import audit_environment, expected_paths


def main() -> int:
    parser = argparse.ArgumentParser(prog="normative_world_model")
    parser.add_argument(
        "command",
        choices=["check-isolation", "check-phase1", "phase1", "phase1-smoke"],
    )
    parser.add_argument("--families", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260715)
    args = parser.parse_args()

    if args.command == "check-isolation":
        failures = audit_environment()
        if failures:
            for failure in failures:
                print(f"FAIL: {failure}")
            return 1
        for key, path in expected_paths().items():
            print(f"OK: {key}={path}")
        print("Isolation audit passed.")
        return 0

    if args.command in {"phase1", "phase1-smoke"}:
        from .generator import run_phase1

        report = run_phase1(
            args.families,
            args.seed,
            run_kind="retained" if args.command == "phase1" else "revision2_smoke",
        )
        print(f"Phase 1 status: {report['status']}")
        print(f"Discovery families: {report['total_discovery_families']}")
        for failure in report["failures"]:
            print(f"FAIL: {failure}")
        return 0 if report["status"] == "PASS" else 1

    if args.command == "check-phase1":
        from .generator import verify_phase1_artifacts

        failures = verify_phase1_artifacts()
        for failure in failures:
            print(f"FAIL: {failure}")
        if failures:
            return 1
        print("Phase-1 artifacts and provenance hashes passed.")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
