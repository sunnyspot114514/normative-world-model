"""Re-evaluate an archived Phase-1 corpus and list decision-label changes only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from normative_world_model.environments.game import simulate_game
from normative_world_model.environments.organization import simulate_organization
from normative_world_model.normative_oracle import NORMATIVE_ORACLE_VERSION, load_profiles


ARMS = {
    "primary": ("source", "primary"),
    "factual_twin": ("factual_twin.source", "factual_twin.result"),
    "actor_value_twin": ("actor_value_twin.source", "actor_value_twin.result"),
    "policy_twin": ("policy_twin.source", "policy_twin.result"),
}


def _at(record: dict[str, Any], dotted_path: str) -> Any:
    value: Any = record
    for part in dotted_path.split("."):
        value = value[part]
    return value


def compare_file(path: Path) -> dict[str, Any]:
    environment = path.stem
    simulate = simulate_game if environment == "game" else simulate_organization
    profiles = load_profiles()
    changes: list[dict[str, Any]] = []
    rows = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        rows += 1
        record = json.loads(line)
        for arm, (source_path, old_result_path) in ARMS.items():
            source = _at(record, source_path)
            old_result = _at(record, old_result_path)
            new_result = simulate(source, profiles)
            for profile_id, new_evaluation in new_result.evaluations.items():
                old_evaluation = old_result["evaluations"][profile_id]
                old_label = (old_evaluation["decision"], old_evaluation["reason"])
                new_label = (new_evaluation["decision"], new_evaluation["reason"])
                if old_label != new_label:
                    changes.append(
                        {
                            "scenario_id": record["scenario_id"],
                            "line_number": line_number,
                            "arm": arm,
                            "profile_id": profile_id,
                            "old_decision": old_label[0],
                            "old_reason": old_label[1],
                            "old_score": old_evaluation["score"],
                            "new_decision": new_label[0],
                            "new_reason": new_label[1],
                            "new_score": new_evaluation["score"],
                        }
                    )
    return {
        "environment": environment,
        "rows": rows,
        "evaluated_labels": rows * len(ARMS) * len(profiles),
        "changed_label_count": len(changes),
        "changes": changes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = {
        "comparison_scope": "decision and reason only; score representation changes are excluded",
        "new_oracle_version": NORMATIVE_ORACLE_VERSION,
        "environments": [
            compare_file(args.corpus_dir / "game.jsonl"),
            compare_file(args.corpus_dir / "organization.jsonl"),
        ],
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
