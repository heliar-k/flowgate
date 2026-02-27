"""Base classes and utilities for FlowGate integration tests.

Integration tests are marked with ``@pytest.mark.integration`` and are skipped
by default unless explicitly selected with ``pytest -m integration``.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
import tempfile


class IntegrationTestBase(unittest.TestCase):
    """Base class for all FlowGate integration tests.

    Provides:
    - A temporary working directory (``self.root``) created per test class.
    - Helper methods for building minimal config files.

    Note:
        All test classes that inherit from this base must be decorated with
        ``@pytest.mark.integration`` to be properly skipped/selected by pytest.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="flowgate_itest_")
        self.root = Path(self._tmpdir)

    def tearDown(self) -> None:
        # Best-effort cleanup; ignore errors so tearDown never masks the
        # original test failure.
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def read_json(self, path: Path) -> Any:
        """Read and parse a JSON file."""
        return json.loads(path.read_text(encoding="utf-8"))

    def read_events(self) -> list[dict[str, Any]]:
        """Read all events from the runtime events log."""
        events_path = self.root / "runtime" / "events.log"
        if not events_path.exists():
            return []
        lines = events_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
