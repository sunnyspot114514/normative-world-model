from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from normative_world_model.phase5_serialization import (
    COMMON_ASSISTANT_PREFIX,
    inspect_tokenizer_packages,
    normalize_hf_publisher_siblings,
    prove_common_prompt_token_equality,
    render_common_base_prompt,
    resolve_publisher_weight_plan,
    validate_public_metadata_path,
)


class _Tokenizer:
    def __init__(self, *, offset: int = 0, rendered: str | None = None) -> None:
        self.offset = offset
        self.rendered = rendered
        self.render_calls = []

    def apply_chat_template(self, messages, **kwargs):
        self.render_calls.append((messages, kwargs))
        return self.rendered or "<common>" + "|".join(item["content"] for item in messages)

    def encode(self, text: str, *, add_special_tokens: bool):
        if add_special_tokens:
            raise AssertionError("special tokens must not be added by encode")
        return [ord(character) + self.offset for character in text]

    def __len__(self):
        return 1_114_112


def _snapshot_report() -> dict:
    return {
        "status": "PASS",
        "core_vocab_identical": True,
        "files": {
            "base": {"tokenizer.json": {"bytes": 10, "sha256": "a" * 64}},
            "agentworld": {"tokenizer.json": {"bytes": 11, "sha256": "b" * 64}},
        },
    }


def _write_tokenizer_package(root: Path, *, extra: bool) -> None:
    added = [
        {
            "id": 3,
            "content": "<shared>",
            "special": True,
            "normalized": False,
            "lstrip": False,
            "rstrip": False,
            "single_word": False,
        }
    ]
    if extra:
        added.append(
            {
                "id": 4,
                "content": "<think>",
                "special": True,
                "normalized": False,
                "lstrip": False,
                "rstrip": False,
                "single_word": False,
            }
        )
    tokenizer = {
        "model": {"type": "BPE", "vocab": {"a": 0, "b": 1}},
        "normalizer": None,
        "pre_tokenizer": {"type": "ByteLevel"},
        "post_processor": None,
        "decoder": {"type": "ByteLevel"},
        "truncation": None,
        "padding": None,
        "added_tokens": added,
    }
    (root / "tokenizer.json").write_text(
        json.dumps(tokenizer, sort_keys=True), encoding="utf-8"
    )
    (root / "tokenizer_config.json").write_text(
        json.dumps({"chat_template": "template-extra" if extra else "template-base"}),
        encoding="utf-8",
    )
    (root / "chat_template.jinja").write_text(
        "template-extra" if extra else "template-base",
        encoding="utf-8",
    )


class Phase5TokenizerPackageTests(unittest.TestCase):
    def test_package_inspection_binds_files_and_reports_only_extras(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "base"
            agent = root / "agent"
            base.mkdir()
            agent.mkdir()
            _write_tokenizer_package(base, extra=False)
            _write_tokenizer_package(agent, extra=True)
            report = inspect_tokenizer_packages(base, agent)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["core_vocab_entries"], 2)
            self.assertEqual(
                report["agentworld_only_added_tokens"]["4"]["content"],
                "<think>",
            )
            self.assertFalse(report["chat_templates_identical"])
            self.assertIn("chat_template.jinja", report["files"]["base"])

    def test_core_token_id_change_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "base"
            agent = root / "agent"
            base.mkdir()
            agent.mkdir()
            _write_tokenizer_package(base, extra=False)
            _write_tokenizer_package(agent, extra=True)
            document = json.loads((agent / "tokenizer.json").read_text(encoding="utf-8"))
            document["model"]["vocab"]["b"] = 2
            (agent / "tokenizer.json").write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "core vocabularies"):
                inspect_tokenizer_packages(base, agent)

    def test_bpe_model_change_outside_vocab_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "base"
            agent = root / "agent"
            base.mkdir()
            agent.mkdir()
            _write_tokenizer_package(base, extra=False)
            _write_tokenizer_package(agent, extra=True)
            document = json.loads((agent / "tokenizer.json").read_text(encoding="utf-8"))
            document["model"]["byte_fallback"] = True
            (agent / "tokenizer.json").write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "section differs: model"):
                inspect_tokenizer_packages(base, agent)

    def test_truncation_and_shared_added_token_attribute_drift_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "base"
            agent = root / "agent"
            base.mkdir()
            agent.mkdir()
            _write_tokenizer_package(base, extra=False)
            _write_tokenizer_package(agent, extra=True)
            document = json.loads((agent / "tokenizer.json").read_text(encoding="utf-8"))
            document["truncation"] = {"max_length": 128}
            (agent / "tokenizer.json").write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "section differs: truncation"):
                inspect_tokenizer_packages(base, agent)

            document["truncation"] = None
            document["added_tokens"][0]["special"] = False
            (agent / "tokenizer.json").write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differ in attributes"):
                inspect_tokenizer_packages(base, agent)

    def test_file_chat_template_is_a_bound_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "base"
            agent = root / "agent"
            base.mkdir()
            agent.mkdir()
            _write_tokenizer_package(base, extra=False)
            _write_tokenizer_package(agent, extra=True)
            for package in (base, agent):
                config_path = package / "tokenizer_config.json"
                document = json.loads(config_path.read_text(encoding="utf-8"))
                document.pop("chat_template")
                config_path.write_text(json.dumps(document), encoding="utf-8")
            report = inspect_tokenizer_packages(base, agent)
            self.assertEqual(report["status"], "PASS")


class Phase5CommonSerializationTests(unittest.TestCase):
    def test_renderer_disables_thinking_and_proof_keeps_all_token_ids(self) -> None:
        base = _Tokenizer()
        agent = _Tokenizer()
        messages = [
            {"role": "system", "content": "synthetic system"},
            {"role": "user", "content": "synthetic user"},
        ]
        rendered = render_common_base_prompt(base, messages)
        kwargs = base.render_calls[0][1]
        self.assertFalse(kwargs["enable_thinking"])
        self.assertFalse(kwargs["add_generation_prompt"])
        self.assertTrue(rendered.endswith(COMMON_ASSISTANT_PREFIX))
        self.assertNotIn("<think>", rendered)
        proof = prove_common_prompt_token_equality(
            [("prompt-1", rendered)],
            base_tokenizer=base,
            agentworld_tokenizer=agent,
            tokenizer_package_report=_snapshot_report(),
        )
        self.assertEqual(proof["prompt_count"], 1)
        self.assertEqual(proof["rows"][0]["token_count"], len(rendered))
        self.assertEqual(len(proof["rows"][0]["token_ids"]), len(rendered))
        self.assertIn("tokenizer_snapshot_binding_sha256", proof)

    def test_renderer_rejects_agentworld_only_control_literals(self) -> None:
        with self.assertRaisesRegex(ValueError, "AgentWorld-only"):
            render_common_base_prompt(_Tokenizer(rendered="history<think>"), [])
        with self.assertRaisesRegex(ValueError, "assistant prefix"):
            render_common_base_prompt(
                _Tokenizer(rendered="history" + COMMON_ASSISTANT_PREFIX),
                [],
            )

    def test_single_token_mismatch_stops_the_proof(self) -> None:
        with self.assertRaisesRegex(ValueError, "token-ID mismatch"):
            prove_common_prompt_token_equality(
                [("prompt-1", "synthetic")],
                base_tokenizer=_Tokenizer(),
                agentworld_tokenizer=_Tokenizer(offset=1),
                tokenizer_package_report=_snapshot_report(),
            )

    def test_proof_hash_binds_tokenizer_snapshot(self) -> None:
        first = prove_common_prompt_token_equality(
            [("prompt-1", "synthetic")],
            base_tokenizer=_Tokenizer(),
            agentworld_tokenizer=_Tokenizer(),
            tokenizer_package_report=_snapshot_report(),
        )
        changed = _snapshot_report()
        changed["files"]["agentworld"]["tokenizer.json"]["sha256"] = "c" * 64
        second = prove_common_prompt_token_equality(
            [("prompt-1", "synthetic")],
            base_tokenizer=_Tokenizer(),
            agentworld_tokenizer=_Tokenizer(),
            tokenizer_package_report=changed,
        )
        self.assertNotEqual(first["proof_sha256"], second["proof_sha256"])


class Phase5PublisherPlanTests(unittest.TestCase):
    def test_weight_plan_is_manifest_driven(self) -> None:
        index = {
            "metadata": {"total_size": 30},
            "weight_map": {
                "layer.0": "model-00001-of-00002.safetensors",
                "layer.1": "model-00002-of-00002.safetensors",
            }
        }
        siblings = [
            {
                "rfilename": "model-00002-of-00002.safetensors",
                "size": 20,
                "lfs": {"oid": "sha256:" + "b" * 64, "size": 20},
            },
            {
                "rfilename": "model-00001-of-00002.safetensors",
                "size": 10,
                "lfs": {"sha256": "a" * 64, "size": 10},
            },
        ]
        plan = resolve_publisher_weight_plan(index, reversed(siblings))
        self.assertEqual(plan["weight_file_count"], 2)
        self.assertEqual(plan["total_weight_bytes"], 30)
        self.assertEqual([row["bytes"] for row in plan["files"]], [10, 20])
        extra = siblings + [
            {
                "rfilename": "stale.safetensors",
                "size": 1,
                "lfs": {"sha256": "c" * 64, "size": 1},
            }
        ]
        extra_plan = resolve_publisher_weight_plan(index, extra)
        self.assertEqual(extra_plan["unreferenced_weight_files"], ["stale.safetensors"])
        self.assertNotEqual(plan["weight_plan_sha256"], extra_plan["weight_plan_sha256"])

    def test_missing_publisher_weight_or_bad_digest_fails(self) -> None:
        index = {"weight_map": {"layer": "model.safetensors"}}
        with self.assertRaisesRegex(ValueError, "lacks referenced weight"):
            resolve_publisher_weight_plan(index, [])
        with self.assertRaisesRegex(ValueError, "not a lowercase SHA-256"):
            resolve_publisher_weight_plan(
                index,
                [
                    {
                        "rfilename": "model.safetensors",
                        "size": 1,
                        "lfs": {"oid": "bad", "size": 1},
                    }
                ],
            )

    def test_raw_sibling_normalization_rejects_bool_size_and_disagreement(self) -> None:
        normalized = normalize_hf_publisher_siblings(
            [
                {
                    "rfilename": "model.safetensors",
                    "size": 4,
                    "lfs": {"oid": "sha256:" + "d" * 64, "size": 4},
                }
            ]
        )
        self.assertEqual(normalized[0]["lfs_sha256"], "d" * 64)
        with self.assertRaisesRegex(ValueError, "invalid size"):
            normalize_hf_publisher_siblings(
                [{"rfilename": "model.safetensors", "size": True}]
            )
        with self.assertRaisesRegex(ValueError, "sizes disagree"):
            normalize_hf_publisher_siblings(
                [
                    {
                        "rfilename": "model.safetensors",
                        "size": 4,
                        "lfs": {"sha256": "d" * 64, "size": 5},
                    }
                ]
            )

    def test_public_metadata_allowlist_excludes_weights_and_path_tricks(self) -> None:
        self.assertEqual(
            validate_public_metadata_path("tokenizer/tokenizer.json"),
            "tokenizer/tokenizer.json",
        )
        for value in ("model.safetensors", "../tokenizer.json", "README.md"):
            with self.assertRaises(ValueError):
                validate_public_metadata_path(value)


if __name__ == "__main__":
    unittest.main()
