from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from normative_world_model.audits import (
    audit_density,
    audit_natural_language,
    audit_model_input_integrity,
    audit_nontriviality,
    audit_split_integrity,
    audit_state_machine_integrity,
    audit_surface_leakage_by_environment,
)
from normative_world_model.generator import (
    external_smoke_acceptance_failures,
    generate_environment_families,
    verify_phase1_artifacts,
)
from normative_world_model.ontology import load_predicate_contract
from normative_world_model.reachability import (
    adjacent_no_conflict_witnesses,
    enumerate_reachability,
)


class PhaseOneTests(unittest.TestCase):
    def test_retained_generation_requires_explicit_external_smoke_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                external_smoke_acceptance_failures(Path(directory)),
                ["external revision-2 smoke acceptance record is missing"],
            )

    def test_external_smoke_acceptance_binds_manifest_and_corpus_hashes(self) -> None:
        import hashlib

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifacts" / "phase1_revision2_smoke"
            artifact.mkdir(parents=True)
            manifest_path = artifact / "provenance_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "files": {
                            "data\\generated\\phase1_revision2_smoke\\game.jsonl": "game-hash",
                            "data\\generated\\phase1_revision2_smoke\\organization.jsonl": "org-hash",
                        }
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            (artifact / "phase1_exit_report.json").write_text(
                json.dumps({"status": "PASS", "run_kind": "revision2_smoke"}),
                encoding="utf-8",
            )
            (artifact / "EXTERNAL_AUDIT_ACCEPTED.json").write_text(
                json.dumps(
                    {
                        "status": "ACCEPTED",
                        "unconditional": True,
                        "conditions": [],
                        "auditor": "external-review-1",
                        "accepted_at": "2026-07-15T20:00:00+08:00",
                        "smoke_provenance_manifest_sha256": hashlib.sha256(
                            manifest_path.read_bytes()
                        ).hexdigest(),
                        "smoke_corpus_sha256": {
                            "data/generated/phase1_revision2_smoke/game.jsonl": "game-hash",
                            "data/generated/phase1_revision2_smoke/organization.jsonl": "org-hash",
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(external_smoke_acceptance_failures(root), [])
            acceptance_path = artifact / "EXTERNAL_AUDIT_ACCEPTED.json"
            conditional = json.loads(acceptance_path.read_text(encoding="utf-8"))
            conditional["conditions"] = ["per-environment Gate C pending"]
            acceptance_path.write_text(json.dumps(conditional), encoding="utf-8")
            self.assertIn(
                "external smoke acceptance still contains unresolved conditions",
                external_smoke_acceptance_failures(root),
            )

    def test_uncertainty_thresholds_have_no_conflict_reachable_witnesses(self) -> None:
        rows = enumerate_reachability(5)
        witnesses = adjacent_no_conflict_witnesses(rows)
        self.assertTrue(all(witnesses.values()))

    def test_exact_threshold_uses_greater_than_or_equal_semantics(self) -> None:
        rows = enumerate_reachability(8)
        exact = next(
            row
            for row in rows
            if row["required"] == 8
            and row["observed"] == 3
            and row["policy_minimum"] == 1
            and not row["conflicting"]
        )
        self.assertEqual(exact["uncertainty"], 0.5)
        self.assertIn("procedure_preserving", exact["escalating_profiles"])
        self.assertNotIn("autonomy_preserving", exact["escalating_profiles"])

    def test_generator_is_deterministic_and_twins_respect_causal_scope(self) -> None:
        for environment, seed in (("game", 11), ("organization", 12)):
            first = generate_environment_families(environment, 12, seed)
            second = generate_environment_families(environment, 12, seed)
            self.assertEqual(
                json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True)
            )
            for family in first:
                self.assertNotEqual(
                    family["primary"]["physical_delta"],
                    family["factual_twin"]["result"]["physical_delta"],
                )
                self.assertEqual(
                    family["primary"]["physical_delta"],
                    family["policy_twin"]["result"]["physical_delta"],
                )
                self.assertIn("actor_values", family["model_input"]["state"])
                self.assertNotIn("turn", family["model_input"]["state"])
                self.assertNotIn("ticket", family["model_input"]["state"])
                self.assertNotEqual(
                    family["source"]["state"]["actor_values"],
                    family["actor_value_twin"]["source"]["state"]["actor_values"],
                )
                self.assertIn("next_state", family["primary"])
                self.assertEqual(len(family["rollout"]), 3)
                self.assertEqual(
                    family["rollout"][0]["next_state"],
                    family["rollout"][1]["pre_state"],
                )
                self.assertEqual(family["temporary_fixture_fields"], [])

    def test_structured_profile_shams_change_only_serialization(self) -> None:
        family = generate_environment_families("game", 1, 99)[0]
        for evaluator in family["evaluator_twins"].values():
            first, second = evaluator["structured_profile_shams"]
            self.assertNotEqual(first, second)
            self.assertEqual(json.loads(first), json.loads(second))

    def test_smoke_corpora_pass_density_and_split_gates(self) -> None:
        gates = load_predicate_contract()["density_gates"]
        for environment, seed in (("game", 20260715), ("organization", 20360718)):
            families = generate_environment_families(environment, 1000, seed)
            density = audit_density(families, gates)
            split = audit_split_integrity(families)
            self.assertEqual(density["status"], "PASS", msg=density["failures"])
            self.assertEqual(split["status"], "PASS", msg=split["failures"])

    def test_v2_state_language_and_nontriviality_gates(self) -> None:
        for environment, seed in (("game", 20260715), ("organization", 20360718)):
            families = generate_environment_families(environment, 300, seed)
            for audit in (
                audit_state_machine_integrity(families),
                audit_natural_language(families),
                audit_nontriviality(families),
                audit_model_input_integrity(families),
            ):
                self.assertEqual(audit["status"], "PASS", msg=audit["failures"])

    def test_gate_c_passes_independently_in_each_environment(self) -> None:
        families = [
            *generate_environment_families("game", 300, 20260715),
            *generate_environment_families("organization", 300, 20360718),
        ]
        result = audit_surface_leakage_by_environment(families, 20960716)
        self.assertEqual(result["status"], "PASS", msg=result["failures"])
        self.assertEqual(set(result["environments"]), {"game", "organization"})
        self.assertTrue(result["pooled_result_cannot_override_environment_failure"])
        for report in result["environments"].values():
            self.assertLessEqual(
                max(view["macro_auc"] for view in report["grouped_tfidf"].values()),
                report["point_gate"],
            )
            self.assertLessEqual(
                report["bootstrap_upper_bound"], report["upper_bound_gate"]
            )

    def test_retained_phase1_artifacts_match_provenance_when_present(self) -> None:
        from pathlib import Path

        artifact = Path(__file__).resolve().parents[1] / "artifacts" / "phase1_v2"
        if artifact.exists():
            self.assertEqual(verify_phase1_artifacts(), [])


if __name__ == "__main__":
    unittest.main()
