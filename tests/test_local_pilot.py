from __future__ import annotations

import unittest

from normative_world_model.local_pilot import (
    build_consistency_pairs,
    encode_sft_record,
    factual_target_token_ids,
    pad_sft_encodings,
)


class _Tokenizer:
    eos_token_id = 99

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        self.assert_no_special_tokens = not add_special_tokens
        return [ord(character) for character in text]

    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool,
        return_offsets_mapping: bool,
    ) -> dict[str, list]:
        if not return_offsets_mapping:
            raise AssertionError("offset mapping was not requested")
        return {
            "input_ids": self.encode(
                text,
                add_special_tokens=add_special_tokens,
            ),
            "offset_mapping": [
                (index, index + 1)
                for index in range(len(text))
            ],
        }


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

    def test_encodes_full_target_once_and_maps_declared_boundary(self) -> None:
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

    def test_padding_preserves_factual_target_positions(self) -> None:
        first = encode_sft_record(
            _Tokenizer(),
            {
                "input_text": "p",
                "target_text": "fact,norm",
                "factual_prefix_text": "fact",
                "normative_suffix_text": ",norm",
            },
            max_sequence_tokens=30,
        )
        second = encode_sft_record(
            _Tokenizer(),
            {
                "input_text": "long",
                "target_text": "fact,norm",
                "factual_prefix_text": "fact",
                "normative_suffix_text": ",norm",
            },
            max_sequence_tokens=30,
        )
        batch = pad_sft_encodings(
            [first, second],
            pad_token_id=0,
        )
        self.assertEqual(len(batch.input_ids[0]), len(batch.input_ids[1]))
        self.assertEqual(factual_target_token_ids(first), [102, 97, 99, 116])
        self.assertEqual(
            sum(batch.attention_mask[0]),
            first.total_tokens,
        )

    def test_builds_semantic_and_surface_pairs_separately(self) -> None:
        records = []
        for profile in (
            "procedure_preserving",
            "harm_averse",
            "autonomy_preserving",
            "efficiency_tolerant",
        ):
            for variant in (0, 1):
                records.append(
                    {
                        "record_id": f"{profile}-{variant}",
                        "profile_id": profile,
                        "profile_surface_variant": variant,
                        "semantic_pair_group": f"semantic-{variant}",
                        "surface_sham_group": f"surface-{profile}",
                    }
                )
        pairs = build_consistency_pairs(records)
        pair_types = {pair.pair_type for pair in pairs}
        self.assertEqual(
            pair_types,
            {"semantic_evaluator", "surface_sham"},
        )
        for pair in pairs:
            if pair.pair_type == "surface_sham":
                self.assertEqual(
                    pair.left["profile_id"],
                    pair.right["profile_id"],
                )
            else:
                self.assertNotEqual(
                    pair.left["profile_id"],
                    pair.right["profile_id"],
                )


if __name__ == "__main__":
    unittest.main()
