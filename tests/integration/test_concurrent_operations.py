"""Concurrent operation tests (non-profile).

These tests focus on thread-safety and correctness of the process supervisor
under parallel usage:
- concurrent ``is_running`` checks
- concurrent ``record_event`` writes
- parallel start/stop of independent services

Note: despite living under ``tests/integration/``, this file is intentionally
*not* marked as ``@pytest.mark.integration`` so it runs under the repo's default
pytest selection (which deselects ``integration`` by default).
"""

from __future__ import annotations

import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from flowgate.core.process import ProcessSupervisor

from .base import IntegrationTestBase

_SLEEP_CMD = [sys.executable, "-c", "import time; time.sleep(120)"]


def _make_runtime_supervisor(root: Path) -> ProcessSupervisor:
    return ProcessSupervisor(root / "runtime")


@pytest.mark.unit
class TestConcurrentProcessSupervisor(IntegrationTestBase):
    """Concurrency regression coverage for ProcessSupervisor."""

    def test_concurrent_is_running_checks(self) -> None:
        sv = _make_runtime_supervisor(self.root)
        sv.start("concurrent-svc", _SLEEP_CMD)
        try:
            results: list[bool] = []
            lock = threading.Lock()

            def check() -> None:
                val = sv.is_running("concurrent-svc")
                with lock:
                    results.append(bool(val))

            threads = [threading.Thread(target=check) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            self.assertEqual(len(results), 10)
            self.assertTrue(
                all(results), f"Some is_running checks returned False: {results}"
            )
        finally:
            sv.stop("concurrent-svc", timeout=3)

    def test_concurrent_record_event_writes_are_valid_jsonl(self) -> None:
        sv = _make_runtime_supervisor(self.root)
        n = 25

        def emit(i: int) -> None:
            sv.record_event("test_event", service=f"svc-{i}", result="success")

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(emit, i) for i in range(n)]
            for f in as_completed(futures):
                f.result()

        events = self.read_events()
        test_events = [e for e in events if e.get("event") == "test_event"]
        self.assertEqual(len(test_events), n)

    def test_parallel_start_and_stop_independent_services(self) -> None:
        sv = _make_runtime_supervisor(self.root)
        service_names = [f"parallel-svc-{i}" for i in range(5)]
        errors: list[str] = []

        def lifecycle(name: str) -> None:
            try:
                sv.start(name, _SLEEP_CMD)
                time.sleep(0.05)
                sv.stop(name, timeout=3)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name}: {exc}")

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(lifecycle, n) for n in service_names]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(
            errors, [], f"Errors during parallel service lifecycle: {errors}"
        )
        for name in service_names:
            self.assertFalse(sv.is_running(name), f"{name} still running after stop")


if __name__ == "__main__":
    unittest.main()
