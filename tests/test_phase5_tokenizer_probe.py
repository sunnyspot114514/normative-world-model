from __future__ import annotations

import unittest

from normative_world_model.phase5_serialization import FORBIDDEN_COMMON_CONTROL_LITERALS
from normative_world_model.phase5_tokenizer_probe import (
    EXPECTED_CONFIG_DIFFERENCES,
    EXPECTED_DEFAULT_EQUIVALENCES,
    _verify_probe_document,
    build_public_tokenizer_probe,
)


class _ProbeTokenizer:
    def __init__(self, checkpoint: str, *, control_offset: int = 0) -> None:
        self.control_offset = control_offset
        self.eos_token = EXPECTED_CONFIG_DIFFERENCES["eos_token"][checkpoint]
        self.eos_token_id = 99
        self.model_max_length = EXPECTED_CONFIG_DIFFERENCES["model_max_length"][checkpoint]
        self.is_fast = True
        self._control_ids = {
            literal: 1000 + index + control_offset
            for index, literal in enumerate(FORBIDDEN_COMMON_CONTROL_LITERALS)
        }

    def __len__(self) -> int:
        return 100_000

    def convert_tokens_to_ids(self, literal: str) -> int:
        return self._control_ids[literal]

    def apply_chat_template(self, messages, **kwargs):
        if kwargs["add_generation_prompt"] is not False:
            raise AssertionError("probe must use the history-only renderer")
        return "<history>" + "|".join(row["content"] for row in messages)

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        if add_special_tokens:
            raise AssertionError("probe must not add special tokens")
        if text in self._control_ids:
            return [self._control_ids[text]]
        if len(text) > 10_000:
            return [index % 997 for index in range(6019)]
        return [index % 997 for index in range(max(1, len(text) // 5))]


def _package_report() -> dict:
    return {
        "status": "PASS",
        "core_vocab_identical": True,
        "tokenizer_config_differences": EXPECTED_CONFIG_DIFFERENCES,
        "normalized_default_equivalences": EXPECTED_DEFAULT_EQUIVALENCES,
        "files": {
            "base": {"tokenizer.json": {"bytes": 1, "sha256": "a" * 64}},
            "agentworld": {"tokenizer.json": {"bytes": 1, "sha256": "b" * 64}},
        },
    }


class Phase5PublicTokenizerProbeTests(unittest.TestCase):
    def test_public_probe_binds_snapshots_and_retains_long_prompt_ids(self) -> None:
        result = build_public_tokenizer_probe(
            metadata_verification={"status": "PASS", "manifest_sha256": "c" * 64},
            package_report=_package_report(),
            base_tokenizer=_ProbeTokenizer("base"),
            agentworld_tokenizer=_ProbeTokenizer("agentworld"),
            runtime_versions={"transformers": "fixture", "tokenizers": "fixture"},
        )
        self.assertEqual(result["status"], "PASS_WITH_LOCK_A_EOS_ACTION")
        self.assertEqual(result["input_tokenization_status"], "PASS")
        self.assertEqual(result["common_prompt_proof"]["prompt_count"], 5)
        long_row = next(
            row
            for row in result["common_prompt_proof"]["rows"]
            if row["prompt_id"] == "long-public"
        )
        self.assertEqual(long_row["token_count"], 6019)
        self.assertLessEqual(long_row["token_count"] + 2048, 8192)
        self.assertEqual(len(result["probe_sha256"]), 64)
        self.assertEqual(_verify_probe_document(result, result)["status"], "PASS")
        tampered = dict(result)
        tampered["input_tokenization_status"] = "FAIL"
        with self.assertRaisesRegex(ValueError, "artifact hash"):
            _verify_probe_document(tampered, result)

    def test_effective_control_token_difference_stops_probe(self) -> None:
        with self.assertRaisesRegex(ValueError, "control-token binding differs"):
            build_public_tokenizer_probe(
                metadata_verification={"status": "PASS"},
                package_report=_package_report(),
                base_tokenizer=_ProbeTokenizer("base"),
                agentworld_tokenizer=_ProbeTokenizer("agentworld", control_offset=1),
                runtime_versions={"transformers": "fixture", "tokenizers": "fixture"},
            )


if __name__ == "__main__":
    unittest.main()
