from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from normative_world_model.phase5_preflight import (
    load_phase5_config,
    phase5_selection_binding,
    select_phase5_population,
    validate_stage2_contract,
    verify_remote_payload,
)

PROFILES = (
    "autonomy_preserving",
    "efficiency_tolerant",
    "harm_averse",
    "procedure_preserving",
)


def _event_record(*, hard: bool) -> dict:
    return {
        "authorized": not hard,
        "approval_required": False,
        "approval_present": False,
        "persistent_change": hard,
        "reversibility": 0.5,
        "recovery_cost": 0.2,
        "stakeholder_count": 1,
        "third_party_impact": False,
        "consent_present": True,
        "private_information_exposed": False,
        "obligation_active": False,
        "obligation_breached": False,
        "policy_minimum_evidence_count": 1,
        "minimum_evidence_present": True,
        "required_evidence_count": 2,
        "observed_evidence_count": 2,
        "conflicting_evidence": False,
        "evidence_complete_and_consistent": True,
        "uncertainty": 0.0,
        "impact_vector": {
            "safety": -0.1,
            "privacy": 0.0,
            "autonomy": 0.1,
            "trust": 0.0,
            "efficiency": 0.2,
            "fairness": 0.0,
            "commitment": 0.0,
        },
    }


def _family(scenario: str, environment: str, *, hard: bool) -> list[dict]:
    model_input = {
        "policy": {
            "prohibited_private_disclosure": True,
            "nonconsensual_harm_threshold": -0.5,
            "policy_minimum_evidence_count": 1,
            "conflict_blocking": False,
        }
    }
    decisions = (
        {profile: "reject" for profile in PROFILES}
        if hard
        else {
            "autonomy_preserving": "allow",
            "efficiency_tolerant": "allow",
            "harm_averse": "reject",
            "procedure_preserving": "escalate",
        }
    )
    rows = []
    for profile in PROFILES:
        target = json.dumps(
            {
                "physical_delta": {"change": 1},
                "event_record": _event_record(hard=hard),
                "normative_decision": decisions[profile],
                "escalation_required": decisions[profile] == "escalate",
                "rollout": [],
            },
            separators=(",", ":"),
        )
        for condition in ("structured", "natural_language"):
            scenario_variants = (None,) if condition == "structured" else (0, 1)
            for scenario_variant in scenario_variants:
                for profile_variant in (0, 1):
                    record_id = (
                        f"{scenario}-{condition}-{scenario_variant}-{profile}-{profile_variant}"
                    )
                    rows.append(
                        {
                            "record_id": record_id,
                            "scenario_id": scenario,
                            "environment": environment,
                            "split": "development",
                            "input_condition": condition,
                            "scenario_surface_variant": scenario_variant,
                            "profile_surface_variant": profile_variant,
                            "profile_id": profile,
                            "input_text": (
                                "Pre-transition source (canonical JSON):\n"
                                + json.dumps(model_input, sort_keys=True, separators=(",", ":"))
                                + "\nEvaluator profile:\n{}"
                                if condition == "structured"
                                else "Synthetic scenario and evaluator profile"
                            ),
                            "target_text": target,
                        }
                    )
    return rows


class Phase5Stage2ContractTests(unittest.TestCase):
    def test_committed_draft_is_closed_for_local_stage2(self) -> None:
        self.assertEqual(validate_stage2_contract(load_phase5_config()), [])

    def test_authorization_or_allowlist_relaxation_fails(self) -> None:
        config = load_phase5_config()
        config["authorization"]["model_download"] = True
        config["synthetic_preflight_remote_payload"][
            "selected_prompt_token_id_sequences_allowed"
        ] = True
        failures = validate_stage2_contract(config)
        self.assertTrue(any("model_download" in item for item in failures))
        self.assertTrue(any("token_id_sequences" in item for item in failures))

    def test_selector_semantics_or_lock_status_drift_fails(self) -> None:
        config = load_phase5_config()
        config["selection"]["target_profile_pairs"].reverse()
        config["locks"]["synthetic_preflight"]["status"] = "PASS"
        failures = validate_stage2_contract(config)
        self.assertTrue(any("target profile pairs" in item for item in failures))
        self.assertTrue(any("locks must remain NOT_BUILT" in item for item in failures))


class Phase5SyntheticSelectorTests(unittest.TestCase):
    def test_selector_is_deterministic_balanced_and_exclusion_safe(self) -> None:
        rows = []
        for environment in ("game", "organization"):
            for index in range(4):
                rows.extend(_family(f"{environment}-d-{index}", environment, hard=False))
            for index in range(3):
                rows.extend(_family(f"{environment}-h-{index}", environment, hard=True))
        excluded = {"game-d-0", "organization-h-0"}
        first = select_phase5_population(
            rows,
            excluded_scenario_ids=excluded,
            seed=17,
            discretionary_per_environment=2,
            hard_policy_per_environment=1,
        )
        second = select_phase5_population(
            reversed(rows),
            excluded_scenario_ids=excluded,
            seed=17,
            discretionary_per_environment=2,
            hard_policy_per_environment=1,
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)
        self.assertTrue(excluded.isdisjoint({item.scenario_id for item in first}))
        self.assertEqual({len(item.presentation_record_ids) for item in first}, {8})
        self.assertEqual(phase5_selection_binding(first)["presentation_count"], 48)

    def test_selector_stops_instead_of_relaxing_a_short_bucket(self) -> None:
        rows = _family("game-d-0", "game", hard=False)
        with self.assertRaisesRegex(ValueError, "insufficient eligible families"):
            select_phase5_population(
                rows,
                excluded_scenario_ids=(),
                seed=1,
                discretionary_per_environment=1,
                hard_policy_per_environment=1,
            )

    def test_surface_sham_target_change_is_rejected(self) -> None:
        rows = _family("game-d-0", "game", hard=False)
        row = next(
            item
            for item in rows
            if item["input_condition"] == "structured"
            and item["profile_id"] == "harm_averse"
            and item["profile_surface_variant"] == 1
        )
        target = json.loads(row["target_text"])
        target["normative_decision"] = "allow"
        row["target_text"] = json.dumps(target)
        with self.assertRaisesRegex(ValueError, "surface variant changes"):
            select_phase5_population(
                rows,
                excluded_scenario_ids=(),
                seed=1,
                discretionary_per_environment=1,
                hard_policy_per_environment=0,
            )

    def test_surface_variant_factual_target_change_is_rejected(self) -> None:
        rows = _family("game-d-0", "game", hard=False)
        row = next(
            item
            for item in rows
            if item["input_condition"] == "natural_language"
            and item["scenario_surface_variant"] == 0
            and item["profile_id"] == "harm_averse"
            and item["profile_surface_variant"] == 1
        )
        target = json.loads(row["target_text"])
        target["physical_delta"]["change"] = 2
        row["target_text"] = json.dumps(target)
        with self.assertRaisesRegex(ValueError, "surface variant changes"):
            select_phase5_population(
                rows,
                excluded_scenario_ids=(),
                seed=1,
                discretionary_per_environment=1,
                hard_policy_per_environment=0,
            )


class Phase5RemotePayloadTests(unittest.TestCase):
    def test_exact_allowlist_builds_a_stable_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "runtime").mkdir()
            (root / "runtime" / "runner.py").write_text("print('synthetic')\n", encoding="utf-8")
            (root / "prompts.json").write_text('[{"kind":"public_synthetic"}]\n', encoding="utf-8")
            declared = {
                "runtime/runner.py": "declared_runtime_source_files",
                "prompts.json": "public_synthetic_inputs",
            }
            first = verify_remote_payload(root, declared)
            second = verify_remote_payload(root, dict(reversed(list(declared.items()))))
            self.assertEqual(first, second)
            self.assertEqual(first["file_count"], 2)

    def test_undeclared_or_forbidden_class_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "runner.py").write_text("pass\n", encoding="utf-8")
            (root / "selected_prompt.txt").write_text("project prompt\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "undeclared"):
                verify_remote_payload(
                    root,
                    {"runner.py": "declared_runtime_source_files"},
                )
            with self.assertRaisesRegex(ValueError, "forbidden payload content class"):
                verify_remote_payload(
                    root,
                    {
                        "runner.py": "declared_runtime_source_files",
                        "selected_prompt.txt": "project_prompt",
                    },
                )


if __name__ == "__main__":
    unittest.main()
