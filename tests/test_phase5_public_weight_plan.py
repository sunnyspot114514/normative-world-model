from __future__ import annotations

import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from normative_world_model.phase5_public_metadata import _download_frozen_sources_to_root
from normative_world_model.phase5_public_weight_plan import (
    _build_public_weight_plan,
    _read_weight_plan,
    _verify_weight_plan_documents,
    _write_weight_plan_once,
)
from tests.test_phase5_public_metadata import SOURCE, _FixtureFetcher, _public_files


def _weight_files() -> dict[str, bytes]:
    files = _public_files()
    files["model.safetensors.index.json"] = json.dumps(
        {
            "metadata": {"total_size": 100.0},
            "weight_map": {"layer": "model-00001-of-00001.safetensors"},
        },
        sort_keys=True,
    ).encode("utf-8")
    return files


class Phase5PublicWeightPlanTests(unittest.TestCase):
    def test_plan_rebuilds_from_verified_metadata_without_weight_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "metadata"
            _download_frozen_sources_to_root(
                (SOURCE,), root, _FixtureFetcher(_weight_files())
            )
            result = _build_public_weight_plan(root, (SOURCE,))
            self.assertEqual(result["status"], "PASS_METADATA_ONLY_NO_WEIGHT_BYTES")
            self.assertEqual(result["format_version"], "phase5-public-weight-plan-v3")
            self.assertEqual(len(result["implementation_sources"]), 4)
            self.assertEqual(result["totals"]["weight_file_count"], 1)
            self.assertEqual(result["totals"]["publisher_weight_bytes"], 123)
            self.assertEqual(result["totals"]["index_declared_tensor_bytes"], 100)
            self.assertEqual(
                result["totals"]["safetensors_container_overhead_bytes"], 23
            )
            self.assertFalse(any(path.suffix == ".safetensors" for path in root.rglob("*")))

            output = Path(temporary) / "plan.json"
            _write_weight_plan_once(output, result)
            stored = _read_weight_plan(output)
            self.assertEqual(_verify_weight_plan_documents(stored, result)["status"], "PASS")
            with self.assertRaises(FileExistsError):
                _write_weight_plan_once(output, result)

    def test_plan_rejects_unreferenced_publisher_weights(self) -> None:
        fetcher = _FixtureFetcher(_weight_files())
        api_document = json.loads(fetcher.api)
        api_document["siblings"].append(
            {
                "rfilename": "stale.safetensors",
                "size": 7,
                "lfs": {"sha256": "e" * 64, "size": 7},
            }
        )
        fetcher.api = json.dumps(api_document, sort_keys=True).encode("utf-8")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "metadata"
            _download_frozen_sources_to_root((SOURCE,), root, fetcher)
            with self.assertRaisesRegex(ValueError, "unreferenced weight"):
                _build_public_weight_plan(root, (SOURCE,))

    def test_plan_reader_rejects_tamper_and_hard_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "metadata"
            _download_frozen_sources_to_root(
                (SOURCE,), root, _FixtureFetcher(_weight_files())
            )
            result = _build_public_weight_plan(root, (SOURCE,))
            output = Path(temporary) / "plan.json"
            _write_weight_plan_once(output, result)
            stored = _read_weight_plan(output)
            tampered = dict(stored)
            tampered["status"] = "PASS"
            with self.assertRaisesRegex(ValueError, "artifact hash"):
                _verify_weight_plan_documents(tampered, result)
            rebuilt_after_source_drift = deepcopy(result)
            source = next(iter(rebuilt_after_source_drift["implementation_sources"]))
            rebuilt_after_source_drift["implementation_sources"][source]["sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "independent rebuild"):
                _verify_weight_plan_documents(stored, rebuilt_after_source_drift)
            hard_link = Path(temporary) / "plan-hard-link.json"
            os.link(output, hard_link)
            with self.assertRaisesRegex(ValueError, "hard links"):
                _read_weight_plan(output)


if __name__ == "__main__":
    unittest.main()
