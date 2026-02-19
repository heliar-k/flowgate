from __future__ import annotations

import unittest
from pathlib import Path

import pytest


@pytest.mark.unit
class IntegrationDocsTests(unittest.TestCase):
    def test_integration_doc_mentions_claude_gateway_support(self):
        text = Path("docs/integration-claude-code-codex.md").read_text(encoding="utf-8")
        self.assertIn("ANTHROPIC_BASE_URL", text)
        self.assertNotIn("Claude Code` 不能直接指向 `FlowGate /v1`", text)
        self.assertIn("Claude Code 可通过", text)


if __name__ == "__main__":
    unittest.main()
