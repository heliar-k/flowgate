from __future__ import annotations

import unittest
from pathlib import Path


class PreCommitConfigTests(unittest.TestCase):
    def test_pre_commit_config_includes_standard_and_ruff_hooks(self):
        path = Path(".pre-commit-config.yaml")
        self.assertTrue(
            path.exists(), ".pre-commit-config.yaml should exist at repo root"
        )

        text = path.read_text(encoding="utf-8")
        required_entries = [
            "repo: https://github.com/pre-commit/pre-commit-hooks",
            "id: check-merge-conflict",
            "id: end-of-file-fixer",
            "id: trailing-whitespace",
            "id: check-yaml",
            "id: check-json",
            "repo: https://github.com/astral-sh/ruff-pre-commit",
            "id: ruff",
            "id: ruff-format",
        ]

        for entry in required_entries:
            self.assertIn(entry, text)


if __name__ == "__main__":
    unittest.main()
