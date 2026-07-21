from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from normative_world_model.phase5_no_gpu_download import (
    verify_no_gpu_download_acceptance,
)

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "configs" / "phase5_no_gpu_download_acceptance.json"
NOW = datetime(2026, 7, 22, 12, 0, 0, tzinfo=UTC)


class Phase5NoGpuDownloadTests(unittest.TestCase):
    def test_exact_source_bound_acceptance_passes(self) -> None:
        result = verify_no_gpu_download_acceptance(
            ACCEPTANCE, repository_root=ROOT, now_utc=NOW
        )
        self.assertEqual(result["status"], "PASS_SOURCE_BOUND_NO_GPU_WEIGHT_PREPARATION")
        self.assertEqual(result["maximum_network_download_bytes"], 71_903_877_960)
        self.assertEqual(result["maximum_additional_data_disk_bytes"], 141_225_192_536)

    def test_self_rehashed_authority_expansion_cannot_replace_source_binding(self) -> None:
        changed = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        changed["authorization"]["gpu_execution"] = True
        changed["acceptance_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "acceptance.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source binding"):
                verify_no_gpu_download_acceptance(path, repository_root=ROOT, now_utc=NOW)

    def test_expired_acceptance_fails(self) -> None:
        with self.assertRaisesRegex(PermissionError, "not currently valid"):
            verify_no_gpu_download_acceptance(
                ACCEPTANCE,
                repository_root=ROOT,
                now_utc=datetime(2026, 7, 24, 0, 0, 0, tzinfo=UTC),
            )

    def test_verifier_has_no_process_network_browser_or_write_surface(self) -> None:
        source = (
            ROOT / "src" / "normative_world_model" / "phase5_no_gpu_download.py"
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
