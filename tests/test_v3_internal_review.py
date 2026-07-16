from __future__ import annotations

import copy
import re
import tomllib
import unittest
from pathlib import Path

from normative_world_model.phase1_v3 import (
    audit_natural_language_v3,
    generate_v3_environment_families,
)


class V3InternalReviewTests(unittest.TestCase):
    def test_v3_reset_cannot_authorize_retained_generation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with (root / "configs" / "preregistration_v3.toml").open("rb") as handle:
            v3 = tomllib.load(handle)
        with (root / "configs" / "preregistration.toml").open("rb") as handle:
            v2 = tomllib.load(handle)
        self.assertTrue(v3["external_acceptance_required_before_retained"])
        self.assertFalse(v3["internal_review_may_authorize_retained"])
        self.assertNotEqual(v3["seeds"]["discovery"], v2["seeds"]["discovery"])
        self.assertNotEqual(v3["seeds"]["confirmation"], v2["seeds"]["confirmation"])
        self.assertEqual(v3["stopping"]["generator_schema_revisions_used"], 1)

    def test_v3_repairs_only_language_and_version_metadata(self) -> None:
        from normative_world_model.generator import generate_environment_families

        for environment, seed in (("game", 101), ("organization", 102)):
            before = generate_environment_families(environment, 80, seed)
            after = generate_v3_environment_families(environment, 80, seed)
            self.assertEqual(len(before), len(after))
            for old, new in zip(before, after, strict=True):
                comparison = copy.deepcopy(new)
                comparison.pop("preregistration_version")
                comparison["generator_revision"] = old["generator_revision"]
                for old_surface, new_surface in zip(
                    old["surface_twins"],
                    comparison["surface_twins"],
                    strict=True,
                ):
                    new_surface["natural_language"] = old_surface["natural_language"]
                for profile_id in old["evaluator_twins"]:
                    comparison["evaluator_twins"][profile_id][
                        "natural_language_profile_shams"
                    ] = old["evaluator_twins"][profile_id][
                        "natural_language_profile_shams"
                    ]
                self.assertEqual(comparison, old)

    def test_v3_language_gate_catches_and_removes_missed_grammar_classes(self) -> None:
        for environment, seed in (
            ("game", 20260716),
            ("organization", 20360719),
        ):
            families = generate_v3_environment_families(environment, 300, seed)
            report = audit_natural_language_v3(families)
            self.assertEqual(report["status"], "PASS", msg=report["failures"])
            metrics = report["metrics"]
            self.assertEqual(metrics["count_agreement_error_count"], 0)
            self.assertEqual(metrics["subject_verb_agreement_error_count"], 0)
            self.assertEqual(metrics["profile_sentence_case_error_count"], 0)
            all_text = "\n".join(
                surface["natural_language"]
                for family in families
                for surface in family["surface_twins"]
            )
            self.assertIsNone(
                re.search(r"\bone (?:clues|records|stakeholders)\b", all_text)
            )
            self.assertIsNone(
                re.search(
                    r"\b(?:plan to (?:disclose|intervene|promise|allocate resource) "
                    r"for the|proposes to (?:read or write file|spend budget|"
                    r"send external message|deploy or delete) across the|"
                    r"permitted acts are|the role permits (?:read or write file|"
                    r"spend budget|send external message|deploy or delete))\b",
                    all_text,
                    re.IGNORECASE,
                )
            )
            self.assertIn('"', all_text)
            for family in families:
                for evaluator in family["evaluator_twins"].values():
                    self.assertTrue(
                        all(
                            ", The uncertainty" not in sham
                            for sham in evaluator[
                                "natural_language_profile_shams"
                            ]
                        )
                    )

            broken = copy.deepcopy(families)
            broken[0]["evaluator_twins"]["procedure_preserving"][
                "natural_language_profile_shams"
            ][1] = broken[0]["evaluator_twins"]["procedure_preserving"][
                "natural_language_profile_shams"
            ][1].replace(
                ", the uncertainty",
                ", The uncertainty",
                1,
            )
            broken_report = audit_natural_language_v3(broken)
            self.assertIn(
                "profile paraphrase sentence-case error",
                broken_report["failures"],
            )

            broken_action = copy.deepcopy(families)
            broken_action[0]["surface_twins"][0]["natural_language"] += (
                " They plan to allocate resource for the group."
                if environment == "game"
                else " The analyst proposes to read or write file across the record."
            )
            broken_action_report = audit_natural_language_v3(broken_action)
            self.assertIn(
                "malformed controlled-language action phrase",
                broken_action_report["failures"],
            )

    def test_independent_auditor_has_no_project_package_import(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "independent-smoke-audit.py"
        )
        source = path.read_text(encoding="utf-8")
        self.assertNotRegex(
            source,
            r"^\s*(?:from|import)\s+normative_world_model",
        )


if __name__ == "__main__":
    unittest.main()
