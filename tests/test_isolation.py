from __future__ import annotations

import unittest
from pathlib import Path

from normative_world_model.isolation import expected_paths, project_root


class IsolationTests(unittest.TestCase):
    def test_all_expected_paths_are_inside_project_root(self) -> None:
        root = project_root().resolve()
        for path in expected_paths(root).values():
            Path(path).resolve().relative_to(root)


if __name__ == "__main__":
    unittest.main()

