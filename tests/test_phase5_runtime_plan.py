from __future__ import annotations

import unittest
from pathlib import Path

from normative_world_model.phase5_preflight import load_phase5_config
from normative_world_model.phase5_runtime_plan import (
    _canonical_sha256,
    build_phase5_runtime_plan,
)
from normative_world_model.phase5_termination_probe import (
    load_termination_probe_config,
)


def _weight_plan() -> dict:
    config = load_phase5_config()
    rows = []
    for checkpoint, file_count, total in (
        ("agentworld", 21, 69_321_314_576),
        ("base", 14, 71_903_877_960),
    ):
        model = config["models"][checkpoint]
        rows.append(
            {
                "checkpoint": checkpoint,
                "repo_id": model["model_id"],
                "revision": model["observed_revision_2026_07_18"],
                "weight_plan": {
                    "files": [
                        {
                            "path": f"model-{index:05d}-of-{file_count:05d}.safetensors",
                            "bytes": total // file_count,
                            "sha256": f"{index:064x}",
                        }
                        for index in range(1, file_count + 1)
                    ],
                    "weight_file_count": file_count,
                    "total_weight_bytes": total,
                    "index_declared_tensor_bytes": total - file_count,
                    "safetensors_container_overhead_bytes": file_count,
                    "unreferenced_weight_files": [],
                    "weight_plan_sha256": ("a" if checkpoint == "agentworld" else "b")
                    * 64,
                },
            }
        )
    return {
        "artifact_sha256": "c" * 64,
        "authorization": {
            "model_download": False,
            "remote_fetch_performed": False,
            "weight_bytes_present": False,
        },
        "checkpoints": rows,
    }


def _build(**overrides) -> dict:
    weight_plan = overrides.pop("public_weight_plan", _weight_plan())
    return build_phase5_runtime_plan(
        config=overrides.pop("config", load_phase5_config()),
        termination_config=overrides.pop(
            "termination_config", load_termination_probe_config()
        ),
        public_weight_plan=weight_plan,
        weight_verification=overrides.pop(
            "weight_verification",
            {
                "status": "PASS",
                "artifact_sha256": weight_plan["artifact_sha256"],
                "model_download": False,
                "weight_bytes_present": False,
                "weight_file_count": 35,
                "publisher_weight_bytes": 141_225_192_536,
            },
        ),
        termination_verification=overrides.pop(
            "termination_verification",
            {
                "status": "PASS_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED",
                "plan_sha256": "d" * 64,
                "http_execution": False,
            },
        ),
        implementation_sources=overrides.pop(
            "implementation_sources",
            {"fixture.py": {"bytes": 1, "sha256": "e" * 64}},
        ),
        **overrides,
    )


class Phase5RuntimePlanTests(unittest.TestCase):
    def test_plan_binds_two_common_language_only_offline_launches(self) -> None:
        plan = _build()
        self.assertEqual(
            plan["status"],
            "LOCAL_RUNTIME_PLAN_PASS_LOCK_A_NOT_BUILT_EXECUTION_NOT_AUTHORIZED",
        )
        self.assertEqual(plan["launch_order"], ["agentworld", "base"])
        self.assertTrue(plan["serve_sequentially"])
        self.assertEqual(len(plan["launch_specs"]), 2)
        self.assertFalse(any(plan["authorization"].values()))
        self.assertEqual(
            plan["common_effective_runtime_contract"]["quantization"], "none"
        )
        self.assertFalse(
            plan["common_effective_runtime_contract"]["trust_remote_code"]
        )
        self.assertEqual(
            plan["runtime_plan_sha256"],
            _canonical_sha256(
                {
                    key: value
                    for key, value in plan.items()
                    if key != "runtime_plan_sha256"
                }
            ),
        )

        normalized_argv = []
        for launch in plan["launch_specs"]:
            argv = list(launch["argv"])
            self.assertEqual(launch["executable"], "vllm")
            self.assertIn("--language-model-only", argv)
            self.assertIn("--generation-config", argv)
            self.assertNotIn("--trust-remote-code", argv)
            self.assertEqual(launch["environment"]["HF_HUB_OFFLINE"], "1")
            self.assertEqual(launch["environment"]["TRANSFORMERS_OFFLINE"], "1")
            self.assertEqual(launch["environment"]["VLLM_USE_FLASHINFER_SAMPLER"], "0")
            self.assertTrue(launch["snapshot_relative_path"].startswith("models/phase5/"))
            self.assertEqual(launch["weight_plan"]["unreferenced_weight_files"], [])
            argv[1] = "<snapshot>"
            argv[argv.index("--served-model-name") + 1] = "<alias>"
            normalized_argv.append(argv)
        self.assertEqual(normalized_argv[0], normalized_argv[1])

    def test_open_authorization_or_language_only_drift_fails(self) -> None:
        opened = load_phase5_config()
        opened["authorization"]["server_rental"] = True
        with self.assertRaises(ValueError):
            _build(config=opened)

        language_drift = load_phase5_config()
        language_drift["runtime"]["language_model_only_base_candidate"] = False
        with self.assertRaises(ValueError):
            _build(config=language_drift)

    def test_weight_or_termination_identity_drift_fails(self) -> None:
        weight_plan = _weight_plan()
        weight_plan["checkpoints"][0]["revision"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "source differ"):
            _build(public_weight_plan=weight_plan)

        with self.assertRaisesRegex(ValueError, "termination plan"):
            _build(
                termination_verification={
                    "status": "PASS_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED",
                    "plan_sha256": "d" * 64,
                    "http_execution": True,
                }
            )

    def test_module_has_no_execution_or_network_client_surface(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "normative_world_model"
            / "phase5_runtime_plan.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "import subprocess",
            "import socket",
            "import urllib",
            "import requests",
            "import httpx",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
