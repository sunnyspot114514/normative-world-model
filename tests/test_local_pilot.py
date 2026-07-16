from __future__ import annotations

import unittest

from normative_world_model.local_pilot import encode_sft_record


class _Tokenizer:
    eos_token_id = 99

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        self.assert_no_special_tokens = not add_special_tokens
        return [ord(character) for character in text]


class LocalPilotTests(unittest.TestCase):
    def test_masks_prompt_and_learns_target_plus_eos(self) -> None:
        tokenizer = _Tokenizer()
        encoded = encode_sft_record(
            tokenizer,
            {"input_text": "ab", "target_text": "cd"},
            max_sequence_tokens=10,
        )
        self.assertEqual(encoded.prompt_tokens, 3)
        self.assertEqual(encoded.target_tokens, 3)
        self.assertEqual(encoded.input_ids, [97, 98, 10, 99, 100, 99])
        self.assertEqual(encoded.labels, [-100, -100, -100, 99, 100, 99])
        self.assertEqual(encoded.factual_target_tokens, 0)
        self.assertEqual(encoded.normative_target_tokens, 3)

    def test_encodes_declared_target_boundary_separately(self) -> None:
        encoded = encode_sft_record(
            _Tokenizer(),
            {
                "input_text": "p",
                "target_text": "fact,norm",
                "factual_prefix_text": "fact",
                "normative_suffix_text": ",norm",
            },
            max_sequence_tokens=20,
        )
        self.assertEqual(encoded.factual_target_tokens, 4)
        self.assertEqual(encoded.normative_target_tokens, 6)
        self.assertEqual(encoded.factual_logit_slice, slice(1, 5))

    def test_rejects_truncation(self) -> None:
        with self.assertRaisesRegex(ValueError, "above max_sequence_tokens"):
            encode_sft_record(
                _Tokenizer(),
                {"input_text": "abcd", "target_text": "efgh"},
                max_sequence_tokens=4,
            )


if __name__ == "__main__":
    unittest.main()
