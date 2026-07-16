"""Build a compact, deterministic external-audit view of the revision-2 smoke corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def leaf_differences(
    left: Any, right: Any, path: tuple[str, ...] = ()
) -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        differences: list[str] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                differences.append(".".join((*path, key)))
            else:
                differences.extend(
                    leaf_differences(left[key], right[key], (*path, key))
                )
        return differences
    return [] if left == right else [".".join(path)]


def variable_article_errors(record: dict[str, Any]) -> list[dict[str, str]]:
    model_input = record["model_input"]
    state = model_input["state"]
    terms = [model_input["action"]["tactic"]]
    if record["environment"] == "game":
        terms.extend([state["surface_context"]["witness"], state["actor"]])
    else:
        terms.extend([state["surface_context"]["observer"], state["role"]])
    errors = []
    for surface in record["surface_twins"]:
        lowered = surface["natural_language"].lower()
        for term in terms:
            match = re.search(rf"\b(?:a|an)\s+{re.escape(term.lower())}\b", lowered)
            if match:
                errors.append(
                    {"surface_id": surface["surface_id"], "match": match.group(0)}
                )
    return errors


def audit_row(record: dict[str, Any], line_number: int, raw_line: bytes) -> dict[str, Any]:
    source = record["source"]
    model_input = record["model_input"]
    forbidden = [
        path
        for path in ("turn", "ticket")
        if path in model_input.get("state", {})
    ]
    twin_paths = {
        name: leaf_differences(source, record[name]["source"])
        for name in ("factual_twin", "actor_value_twin", "policy_twin")
    }
    primary_delta = record["primary"]["physical_delta"]
    physical_relations = {
        "factual_changed": record["factual_twin"]["result"]["physical_delta"]
        != primary_delta,
        "actor_changed": record["actor_value_twin"]["result"]["physical_delta"]
        != primary_delta,
        "policy_preserved": record["policy_twin"]["result"]["physical_delta"]
        == primary_delta,
    }
    rollout = record["rollout"]
    rollout_chain = len(rollout) == 3 and all(
        previous["next_state"] == current["pre_state"]
        for previous, current in zip(rollout, rollout[1:], strict=False)
    )
    boundaries = []
    result_paths = {
        "primary": record["primary"],
        "factual_twin": record["factual_twin"]["result"],
        "actor_value_twin": record["actor_value_twin"]["result"],
        "policy_twin": record["policy_twin"]["result"],
    }
    for arm, result in result_paths.items():
        for profile_id, evaluation in result["evaluations"].items():
            if evaluation["score_margin_to_boundary"] == 0.0:
                boundaries.append(
                    {
                        "arm": arm,
                        "profile_id": profile_id,
                        "decision": evaluation["decision"],
                        "reason": evaluation["reason"],
                        "score": evaluation["score"],
                    }
                )
    computed_model_input_hash = sha256_bytes(canonical_bytes(model_input))
    return {
        "environment": record["environment"],
        "line_number": line_number,
        "scenario_id": record["scenario_id"],
        "raw_line_sha256": sha256_bytes(raw_line),
        "stored_model_input_sha256": record["model_input_sha256"],
        "computed_model_input_sha256": computed_model_input_hash,
        "model_input_hash_matches": computed_model_input_hash
        == record["model_input_sha256"],
        "forbidden_model_input_ids": forbidden,
        "variable_article_errors": variable_article_errors(record),
        "twin_source_difference_paths": twin_paths,
        "twin_source_scope_valid": {
            "factual_twin": len(twin_paths["factual_twin"]) == 1
            and twin_paths["factual_twin"][0].startswith("state."),
            "actor_value_twin": len(twin_paths["actor_value_twin"]) == 1
            and twin_paths["actor_value_twin"][0].startswith("state.actor_values."),
            "policy_twin": len(twin_paths["policy_twin"]) == 1
            and twin_paths["policy_twin"][0].startswith("policy."),
        },
        "physical_relations": physical_relations,
        "rollout_chain_valid": rollout_chain,
        "exact_boundary_evaluations": boundaries,
        "natural_language_sha256": [
            sha256_bytes(surface["natural_language"].encode("utf-8"))
            for surface in record["surface_twins"]
        ],
    }


def sample_view(record: dict[str, Any], index: dict[str, Any]) -> dict[str, Any]:
    view = {
        "audit_index": index,
        "schema_version": record["schema_version"],
        "generator_revision": record["generator_revision"],
        "scenario_id": record["scenario_id"],
        "environment": record["environment"],
        "split": record["split"],
        "source": record["source"],
        "model_input": record["model_input"],
        "primary": record["primary"],
        "surface_twins": record["surface_twins"],
        "rollout": record["rollout"],
    }
    for name in ("factual_twin", "actor_value_twin", "policy_twin"):
        view[name] = {
            "source": record[name]["source"],
            "model_input": record[name]["model_input"],
            "result": record[name]["result"],
        }
    return view


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--sample-per-environment", type=int, default=20)
    args = parser.parse_args()
    root = args.project_root.resolve()
    data_dir = root / "data" / "generated" / "phase1_revision2_smoke"
    artifact_dir = root / "artifacts" / "phase1_revision2_smoke"
    output_dir = artifact_dir / "external_audit_bundle"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    all_indices: list[dict[str, Any]] = []
    records: dict[str, dict[str, Any]] = {}
    corpus_hashes = {}
    for environment in ("game", "organization"):
        path = data_dir / f"{environment}.jsonl"
        corpus_hashes[str(path.relative_to(root)).replace("\\", "/")] = sha256_bytes(
            path.read_bytes()
        )
        with path.open("rb") as handle:
            for line_number, raw_line_with_newline in enumerate(handle, start=1):
                raw_line = raw_line_with_newline.rstrip(b"\r\n")
                if not raw_line:
                    continue
                record = json.loads(raw_line)
                index = audit_row(record, line_number, raw_line)
                all_indices.append(index)
                records[record["scenario_id"]] = record

    ranked = sorted(
        all_indices,
        key=lambda item: sha256_bytes(item["scenario_id"].encode("utf-8")),
    )
    selected_ids = set()
    for environment in ("game", "organization"):
        selected_ids.update(
            item["scenario_id"]
            for item in ranked
            if item["environment"] == environment
        )
        environment_ids = [
            item["scenario_id"]
            for item in ranked
            if item["environment"] == environment
        ]
        selected_ids.difference_update(environment_ids[args.sample_per_environment :])
    selected_ids.update(
        item["scenario_id"]
        for item in all_indices
        if item["exact_boundary_evaluations"]
        or not item["physical_relations"]["actor_changed"]
    )
    selected_indices = [
        item for item in all_indices if item["scenario_id"] in selected_ids
    ]

    index_path = output_dir / "row_audit_index.jsonl"
    index_path.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for item in all_indices
        ),
        encoding="utf-8",
    )
    sample_path = output_dir / "deterministic_sample.jsonl"
    sample_path.write_text(
        "".join(
            json.dumps(
                sample_view(records[item["scenario_id"]], item),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for item in selected_indices
        ),
        encoding="utf-8",
    )
    for name in ("phase1_exit_report.json", "provenance_manifest.json"):
        shutil.copyfile(artifact_dir / name, output_dir / name)
    shutil.copyfile(
        data_dir / "confirmation_reservation.json",
        output_dir / "confirmation_reservation.json",
    )
    contract_dir = output_dir / "contracts"
    contract_dir.mkdir()
    for relative in (
        Path("PREREGISTRATION.md"),
        Path("docs/NORMATIVE_PREDICATE_CONTRACT.md"),
        Path("docs/EVALUATOR_PROFILES.md"),
        Path("docs/LEAKAGE_AUDIT_SPEC.md"),
        Path("docs/METRIC_COMPARATOR_V2_1.md"),
        Path("docs/EXTERNAL_SMOKE_ACCEPTANCE.md"),
        Path("docs/EXTERNAL_AUDIT_ADJUDICATION.md"),
    ):
        destination = contract_dir / relative.name
        shutil.copyfile(root / relative, destination)
    write_json(
        output_dir / "EXTERNAL_AUDIT_ACCEPTED.template.json",
        {
            "status": "REVIEW_REQUIRED",
            "unconditional": False,
            "conditions": [],
            "auditor": "",
            "accepted_at": "",
            "smoke_provenance_manifest_sha256": sha256_bytes(
                (artifact_dir / "provenance_manifest.json").read_bytes()
            ),
            "smoke_corpus_sha256": corpus_hashes,
            "notes": "",
        },
    )

    summary = {
        "status": "READY_FOR_EXTERNAL_AUDIT",
        "full_corpus_row_count": len(all_indices),
        "sample_row_count": len(selected_indices),
        "sample_selection": (
            "lowest SHA256-ranked scenario IDs per environment, plus every exact-boundary "
            "or actor-physical-insensitive row"
        ),
        "full_corpus_hashes": corpus_hashes,
        "index_checks": {
            "model_input_hash_mismatches": sum(
                not item["model_input_hash_matches"] for item in all_indices
            ),
            "forbidden_model_input_id_rows": sum(
                bool(item["forbidden_model_input_ids"]) for item in all_indices
            ),
            "variable_article_error_rows": sum(
                bool(item["variable_article_errors"]) for item in all_indices
            ),
            "invalid_twin_source_scope_rows": sum(
                not all(item["twin_source_scope_valid"].values()) for item in all_indices
            ),
            "invalid_rollout_chain_rows": sum(
                not item["rollout_chain_valid"] for item in all_indices
            ),
            "exact_boundary_rows": sum(
                bool(item["exact_boundary_evaluations"]) for item in all_indices
            ),
            "actor_physical_insensitive_rows": sum(
                not item["physical_relations"]["actor_changed"] for item in all_indices
            ),
        },
    }
    write_json(output_dir / "audit_bundle_summary.json", summary)

    readme = """# Revision-2 smoke external-audit bundle

Status: **READY FOR EXTERNAL AUDIT; NOT AUTHORIZED FOR RETAINED GENERATION**

The full smoke corpus contains 300 families per environment. `row_audit_index.jsonl` covers every
row and records exact raw-line hashes, model-input hashes, forbidden-ID checks, variable-article
checks, one-leaf twin intervention paths, physical sensitivity/invariance, rollout chaining, and
exact oracle-boundary cases. `deterministic_sample.jsonl` contains human-readable source, surfaces,
targets, twin sources/results, and rollouts for the fixed sample plus every boundary or actor-
insensitive row.

Audit acceptance requires independently checking:

1. sample natural-language grammar and semantic fidelity;
2. zero `turn`/`ticket` fields in model input;
3. one-leaf intervention scope for every twin;
4. exact upper/lower boundary labels under decimal semantics;
5. chained rollout state equality and primary H1 equality;
6. per-field state-to-marker cardinality in the exit report;
7. exact corpus hashes against the provenance manifest.

After every condition is resolved, fill `EXTERNAL_AUDIT_ACCEPTED.template.json`, change its status
to `ACCEPTED`, set `unconditional` to `true`, keep `conditions` empty, and place it at
`artifacts/phase1_revision2_smoke/EXTERNAL_AUDIT_ACCEPTED.json`. The retained generator verifies
the unconditional status and every bound hash before it writes any corpus file.

The compact bundle is an inspection aid, not a replacement for the two full JSONL files. Any
questionable row is addressable by environment, line number, scenario ID, and raw-line hash.
The `contracts/` directory contains the exact human-readable contracts bound by the refreshed
provenance manifest.

Hash preimages are exact byte contracts. `natural_language_sha256` hashes the stored natural-
language string encoded as UTF-8 with no normalization or newline. `raw_line_sha256` hashes the
UTF-8 JSONL record after removing only its CR/LF separator. `model_input_sha256` hashes UTF-8
canonical JSON with sorted keys, compact separators, and non-ASCII characters preserved.
"""
    (output_dir / "AUDIT_README.md").write_text(readme, encoding="utf-8")

    manifest_files = {}
    for path in sorted(item for item in output_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(output_dir).as_posix()
        if relative == "bundle_manifest.json":
            continue
        manifest_files[relative] = sha256_bytes(path.read_bytes())
    write_json(
        output_dir / "bundle_manifest.json",
        {"files": manifest_files, "summary": summary},
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
