"""Base classes and utilities for FlowGate integration tests.

Integration tests are marked with ``@pytest.mark.integration`` and are skipped
by default unless explicitly selected with ``pytest -m integration``.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


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

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def make_config(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a minimal valid FlowGate configuration rooted at ``self.root``."""
        runtime_dir = str(self.root / "runtime")
        cfg: dict[str, Any] = {
            "config_version": 2,
            "paths": {
                "runtime_dir": runtime_dir,
                "active_config": str(self.root / "runtime" / "litellm.active.yaml"),
                "state_file": str(self.root / "runtime" / "state.json"),
                "log_file": str(self.root / "runtime" / "events.log"),
            },
            "services": {
                "litellm": {
                    "command": {
                        "args": [sys.executable, "-c", "import time; time.sleep(120)"]
                    },
                    "host": "127.0.0.1",
                    "port": 14100,
                    "readiness_path": "/health",
                },
                "cliproxyapi_plus": {
                    "command": {
                        "args": [sys.executable, "-c", "import time; time.sleep(120)"]
                    },
                    "host": "127.0.0.1",
                    "port": 14101,
                    "readiness_path": "/health",
                },
            },
            "litellm_base": {
                "model_list": [
                    {
                        "model_name": "router-default",
                        "litellm_params": {"model": "openai/gpt-4o"},
                    }
                ],
                "router_settings": {},
                "litellm_settings": {"num_retries": 1},
            },
            "profiles": {
                "reliability": {"litellm_settings": {"num_retries": 3, "cooldown_time": 60}},
                "balanced": {"litellm_settings": {"num_retries": 2, "cooldown_time": 30}},
                "cost": {"litellm_settings": {"num_retries": 1, "cooldown_time": 10}},
            },
            "auth": {"providers": {}},
            "secret_files": [],
        }
        if extra:
            cfg.update(extra)
        return cfg

    def write_config(self, cfg: dict[str, Any] | None = None) -> Path:
        """Write *cfg* (or a default config) to ``self.root/flowgate.yaml``."""
        if cfg is None:
            cfg = self.make_config()
        path = self.root / "flowgate.yaml"
        path.write_text(json.dumps(cfg), encoding="utf-8")
        return path

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
