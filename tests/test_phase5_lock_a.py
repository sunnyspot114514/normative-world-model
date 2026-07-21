from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime
from pathlib import Path

from normative_world_model.phase5_lock_a import (
    LOCK_A_ACCEPTED_STATUS,
    LOCK_A_AUTHORIZATION,
    LOCK_A_FORMAT_VERSION,
    verify_lock_a_acceptance,
)
from normative_world_model.phase5_public_metadata import _canonical_sha256

NOW = datetime(2026, 7, 22, 0, 0, 0, tzinfo=UTC)


def _record() -> dict:
    record = {
        "format_version": LOCK_A_FORMAT_VERSION,
        "status": LOCK_A_ACCEPTED_STATUS,
        "source_commit": "1" * 40,
        "client_plan_sha256": "2" * 64,
        "client_plan_file_sha256": "3" * 64,
        "runtime_bindings_sha256": "4" * 64,
        "remote_environment_manifest_sha256": "5" * 64,
        "weight_download_plan_sha256": "6" * 64,
        "provider_quote": {
            "provider": "AutoDL",
            "currency": "CNY",
            "gpu_model": "RTX PRO 6000",
            "gpu_count": 1,
            "gpu_memory_bytes": 96 * 1024**3,
            "gpu_hourly_price_minor": 598,
            "storage_daily_price_minor": 158,
            "quote_evidence_sha256": "7" * 64,
        },
        "limits": {
            "currency": "CNY",
            "maximum_spend_minor": 6000,
            "whole_rental_wall_clock_seconds": 10 * 60 * 60,
            "maximum_download_bytes": 150 * 1024**3,
            "minimum_free_data_disk_bytes": 182 * 1024**3,
            "minimum_post_download_free_bytes": 32 * 1024**3,
        },
        "authorization": dict(LOCK_A_AUTHORIZATION),
        "governance": {
            "confirmation_status": "RESERVED_NOT_GENERATED",
            "formal_scientific_execution_started": False,
            "retained_data_available_to_remote": False,
            "next_stage_unlocked": "SYNTHETIC_PREFLIGHT_ONLY",
        },
        "validity": {
            "not_before_utc": "2026-07-21T00:00:00Z",
            "expires_utc": "2026-07-24T00:00:00Z",
        },
        "review_record_sha256s": ["8" * 64, "9" * 64],
        "operator_approval_sha256": "a" * 64,
    }
    record["acceptance_sha256"] = _canonical_sha256(record)
    return record


def _verify(record: dict, *, expected: str | None = None, now: datetime = NOW) -> dict:
    return verify_lock_a_acceptance(
        record,
        expected_acceptance_sha256=expected or record["acceptance_sha256"],
        expected_client_plan_sha256="2" * 64,
        expected_runtime_bindings_sha256="4" * 64,
        now_utc=now,
    )


class Phase5LockATests(unittest.TestCase):
    def test_exact_externally_bound_synthetic_only_acceptance_passes(self) -> None:
        result = _verify(_record())
        self.assertEqual(result["status"], "PASS_EXTERNALLY_BOUND_LOCK_A_ACCEPTANCE")
        self.assertEqual(result["maximum_spend_minor"], 6000)
        self.assertEqual(result["whole_rental_wall_clock_seconds"], 36_000)

    def test_in_memory_self_authorization_cannot_replace_external_hash(self) -> None:
        original = _record()
        changed = copy.deepcopy(original)
        changed["limits"]["maximum_spend_minor"] = 99_999
        changed["acceptance_sha256"] = _canonical_sha256(
            {key: value for key, value in changed.items() if key != "acceptance_sha256"}
        )
        with self.assertRaisesRegex(ValueError, "external binding"):
            _verify(changed, expected=original["acceptance_sha256"])

    def test_expired_or_overlong_acceptance_fails(self) -> None:
        expired = _record()
        with self.assertRaisesRegex(PermissionError, "not currently valid"):
            _verify(
                expired,
                now=datetime(2026, 7, 25, 0, 0, 0, tzinfo=UTC),
            )
        overlong = _record()
        overlong["validity"]["expires_utc"] = "2026-08-01T00:00:00Z"
        overlong["acceptance_sha256"] = _canonical_sha256(
            {key: value for key, value in overlong.items() if key != "acceptance_sha256"}
        )
        with self.assertRaisesRegex(ValueError, "validity window"):
            _verify(overlong)

    def test_authority_governance_and_review_drift_fail(self) -> None:
        opened = _record()
        opened["authorization"]["scientific_execution"] = True
        opened["acceptance_sha256"] = _canonical_sha256(
            {key: value for key, value in opened.items() if key != "acceptance_sha256"}
        )
        with self.assertRaisesRegex(PermissionError, "synthetic-only"):
            _verify(opened)
        duplicate_review = _record()
        duplicate_review["review_record_sha256s"] = ["8" * 64, "8" * 64]
        duplicate_review["acceptance_sha256"] = _canonical_sha256(
            {
                key: value
                for key, value in duplicate_review.items()
                if key != "acceptance_sha256"
            }
        )
        with self.assertRaisesRegex(ValueError, "two distinct review"):
            _verify(duplicate_review)

    def test_disk_budget_and_quote_are_machine_checked(self) -> None:
        no_headroom = _record()
        no_headroom["limits"]["minimum_post_download_free_bytes"] = 8 * 1024**3
        no_headroom["acceptance_sha256"] = _canonical_sha256(
            {key: value for key, value in no_headroom.items() if key != "acceptance_sha256"}
        )
        with self.assertRaisesRegex(ValueError, "below 16 GiB"):
            _verify(no_headroom)
        wrong_provider = _record()
        wrong_provider["provider_quote"]["provider"] = "unbound-provider"
        wrong_provider["acceptance_sha256"] = _canonical_sha256(
            {key: value for key, value in wrong_provider.items() if key != "acceptance_sha256"}
        )
        with self.assertRaisesRegex(ValueError, "quote identity"):
            _verify(wrong_provider)

    def test_verifier_has_no_process_network_browser_or_write_surface(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "normative_world_model"
            / "phase5_lock_a.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "import subprocess",
            "import socket",
            "import requests",
            "import httpx",
            "urllib.request",
            "open(\"w",
            ".write_",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
