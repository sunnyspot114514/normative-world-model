from __future__ import annotations

import unittest

from normative_world_model.phase3_schema_gate import (
    development_selection_binding,
    select_unique_development_records,
)


class PhaseThreeSchemaGateTests(unittest.TestCase):
    def test_development_selection_is_balanced_and_scenario_unique(self) -> None:
        records = []
        for environment in ("game", "organization"):
            for scenario in range(12):
                for profile in (
                    "autonomy_preserving",
                    "efficiency_tolerant",
                    "harm_averse",
                    "procedure_preserving",
                ):
                    records.append(
                        {
                            "record_id": (
                                f"{environment}-{scenario}-{profile}"
                            ),
                            "scenario_id": f"{environment}-{scenario}",
                            "environment": environment,
                            "split": "development",
                            "input_condition": "structured",
                            "profile_surface_variant": 0,
                            "profile_id": profile,
                        }
                    )
        selected = select_unique_development_records(records)
        self.assertEqual(len(selected), 16)
        self.assertEqual(
            len({record["scenario_id"] for record in selected}),
            16,
        )
        binding = development_selection_binding(records)
        self.assertEqual(binding["development_generation_count"], 16)
        self.assertEqual(binding["development_scenario_count"], 16)
        self.assertTrue(
            all(
                count == 2
                for count in binding["development_bucket_counts"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
