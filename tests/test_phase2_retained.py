from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from normative_world_model.phase2_retained import (
    _id_hash,
    _write_jsonl_gzip,
)


class PhaseTwoRetainedTests(unittest.TestCase):
    def test_id_hash_is_order_invariant_and_count_sensitive(self) -> None:
        self.assertEqual(_id_hash(["b", "a"]), _id_hash(["a", "b"]))
        self.assertNotEqual(_id_hash(["a"]), _id_hash(["a", "a"]))

    def test_gzip_export_is_byte_deterministic(self) -> None:
        records = [
            {"scenario_id": "one", "value": 1},
            {"scenario_id": "two", "value": 2},
        ]
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl.gz"
            second = Path(directory) / "second.jsonl.gz"
            count_a, hash_a = _write_jsonl_gzip(first, records)
            count_b, hash_b = _write_jsonl_gzip(second, records)
            self.assertEqual((count_a, hash_a), (count_b, hash_b))
            with gzip.open(first, "rt", encoding="utf-8") as handle:
                rows = [json.loads(line) for line in handle]
            self.assertEqual(rows, records)


if __name__ == "__main__":
    unittest.main()
