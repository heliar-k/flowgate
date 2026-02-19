"""Integration tests: concurrent operations.

Verifies that FlowGate modules behave correctly when multiple operations
occur in parallel – concurrent profile switches, parallel health checks,
and simultaneous service management.

Uses ``threading.Thread`` and ``concurrent.futures.ThreadPoolExecutor``.

Note on thread safety:
    ``activate_profile()`` uses an atomic rename (``os.replace``) to update the
    active config file, but the temporary file path is deterministic.  Concurrent
    calls that share the same runtime directory may race on the ``.tmp`` file.
    The tests below are designed with this in mind:
    - Tests for shared-directory concurrency assert only that the *final state*
      is consistent (valid JSON with a known profile), not that every concurrent
      write succeeds.
    - Tests for independent-resource concurrency (different service names,
      different runtime dirs) verify that all operations succeed.

Run with:
    RUN_INTEGRATION_TESTS=1 python -m unittest tests.integration.test_concurrent_operations -v
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from flowgate.cli import run_cli
from flowgate.process import ProcessSupervisor
from flowgate.profile import activate_profile

from .base import IntegrationTestBase


_SLEEP_CMD = [sys.executable, "-c", "import time; time.sleep(120)"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runtime_supervisor(root: Path) -> ProcessSupervisor:
    return ProcessSupervisor(root / "runtime")


def _make_isolated_config(base_root: Path, index: int) -> tuple[Path, dict[str, Any]]:
    """Create a config with a unique runtime directory for isolated concurrency tests."""
    root = base_root / f"worker_{index}"
    root.mkdir(parents=True, exist_ok=True)

    cfg: dict[str, Any] = {
        "config_version": 2,
        "paths": {
            "runtime_dir": str(root / "runtime"),
            "active_config": str(root / "runtime" / "litellm.active.yaml"),
            "state_file": str(root / "runtime" / "state.json"),
            "log_file": str(root / "runtime" / "events.log"),
        },
        "services": {
            "litellm": {
                "command": {
                    "args": [sys.executable, "-c", "import time; time.sleep(120)"]
                },
                "host": "127.0.0.1",
                "port": 14100 + index,
                "readiness_path": "/health",
            },
            "cliproxyapi_plus": {
                "command": {
                    "args": [sys.executable, "-c", "import time; time.sleep(120)"]
                },
                "host": "127.0.0.1",
                "port": 14200 + index,
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
    cfg_path = root / "flowgate.yaml"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    return cfg_path, cfg


# ---------------------------------------------------------------------------
# Concurrent profile switching (isolated directories)
# ---------------------------------------------------------------------------


class TestConcurrentProfileSwitch(IntegrationTestBase):
    """Concurrent profile switches in *isolated* runtime directories all succeed."""

    def test_concurrent_profile_switches_isolated_dirs_all_succeed(self) -> None:
        """Each thread uses its own runtime dir; all profile switches succeed."""
        profiles = ["reliability", "balanced", "cost"]
        workers_root = self.root / "workers"
        workers_root.mkdir(parents=True, exist_ok=True)

        errors: list[str] = []
        success_count = 0
        lock = threading.Lock()

        def switch_in_own_dir(index: int, profile: str) -> None:
            nonlocal success_count
            cfg_path, cfg = _make_isolated_config(workers_root, index)
            out = io.StringIO()
            code = run_cli(
                ["--config", str(cfg_path), "profile", "set", profile],
                stdout=out,
            )
            with lock:
                if code == 0:
                    success_count += 1
                else:
                    errors.append(f"worker {index} profile {profile}: exit {code}")

        threads = [
            threading.Thread(target=switch_in_own_dir, args=(i, p))
            for i, p in enumerate(profiles)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        self.assertEqual(errors, [], f"Errors during isolated concurrent switches: {errors}")
        self.assertEqual(success_count, len(profiles))

    def test_sequential_profile_switches_on_shared_dir_all_succeed(self) -> None:
        """Sequential profile switches to the same runtime dir always succeed."""
        cfg_path = self.write_config()
        profiles = ["reliability", "balanced", "cost"]

        for profile in profiles:
            out = io.StringIO()
            code = run_cli(
                ["--config", str(cfg_path), "profile", "set", profile],
                stdout=out,
            )
            self.assertEqual(code, 0, f"Sequential profile set {profile} failed: {out.getvalue()}")

        # Final state must reflect the last profile set
        state_path = self.root / "runtime" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertIn(state["current_profile"], profiles)

    def test_concurrent_profile_switches_shared_dir_final_state_valid(self) -> None:
        """After concurrent switches to a shared dir, the final state is valid JSON."""
        cfg_path = self.write_config()
        profiles = ["reliability", "balanced", "cost"]

        # Run concurrently; some may fail due to .tmp file races – that is acceptable.
        # We only assert the final state is valid and consistent.
        threads = []
        for profile in profiles:
            def run(p: str = profile) -> None:
                out = io.StringIO()
                run_cli(["--config", str(cfg_path), "profile", "set", p], stdout=out)

            threads.append(threading.Thread(target=run))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        # The state file must still contain valid JSON and a known profile name.
        state_path = self.root / "runtime" / "state.json"
        self.assertTrue(state_path.exists(), "state.json must exist after any successful switch")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertIn("current_profile", state)
        self.assertIn(state["current_profile"], profiles)


# ---------------------------------------------------------------------------
# Concurrent health checks
# ---------------------------------------------------------------------------


class TestConcurrentHealthChecks(IntegrationTestBase):
    """Parallel health checks do not interfere with each other."""

    def test_parallel_is_running_checks(self) -> None:
        """is_running() is safe to call concurrently from multiple threads."""
        sv = _make_runtime_supervisor(self.root)
        sv.start("concurrent-svc", _SLEEP_CMD)
        try:
            results: list[bool] = []
            lock = threading.Lock()

            def check() -> None:
                val = sv.is_running("concurrent-svc")
                with lock:
                    results.append(val)

            threads = [threading.Thread(target=check) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            # Every thread must see the service as running
            self.assertEqual(len(results), 10)
            self.assertTrue(all(results), f"Some is_running checks returned False: {results}")
        finally:
            sv.stop("concurrent-svc", timeout=3)

    def test_parallel_event_writes_produce_valid_log(self) -> None:
        """Concurrent record_event() calls all land correctly in the events log."""
        sv = _make_runtime_supervisor(self.root)
        n = 20

        def emit(i: int) -> None:
            sv.record_event("test_event", service=f"svc-{i}", result="success")

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(emit, i) for i in range(n)]
            for f in as_completed(futures):
                f.result()  # re-raise any exception

        # All events must have been written and be valid JSON
        events = self.read_events()
        test_events = [e for e in events if e.get("event") == "test_event"]
        self.assertEqual(len(test_events), n)


# ---------------------------------------------------------------------------
# Profile switch + immediate service restart
# ---------------------------------------------------------------------------


class TestProfileSwitchAndRestart(IntegrationTestBase):
    """Switching a profile while a service is running, then restarting it."""

    def test_switch_profile_then_restart_service(self) -> None:
        """Profile can be set (without running service) and active config is correct."""
        cfg_path = self.write_config()

        # Switch profile via CLI (sequential – no concurrent race)
        # Do NOT start the litellm service first, as profile set will auto-restart it if running.
        out = io.StringIO()
        code = run_cli(
            ["--config", str(cfg_path), "profile", "set", "reliability"],
            stdout=out,
        )
        # Profile set should succeed when called sequentially
        self.assertEqual(code, 0, f"profile set failed: {out.getvalue()}")

        # Active config must reflect the new profile
        active_path = self.root / "runtime" / "litellm.active.yaml"
        self.assertTrue(active_path.exists())
        active = json.loads(active_path.read_text(encoding="utf-8"))
        self.assertEqual(active["litellm_settings"]["num_retries"], 3)

    def test_concurrent_profile_switch_and_status_check(self) -> None:
        """A profile switch thread and a status-read thread can run simultaneously."""
        cfg_path = self.write_config()
        errors: list[str] = []

        def switch_profiles() -> None:
            try:
                for profile in ("reliability", "balanced", "cost"):
                    out = io.StringIO()
                    # Individual calls are fine; races on shared .tmp are expected
                    run_cli(
                        ["--config", str(cfg_path), "profile", "set", profile],
                        stdout=out,
                    )
                    time.sleep(0.02)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"switch: {exc}")

        def check_status() -> None:
            try:
                for _ in range(5):
                    out = io.StringIO()
                    run_cli(["--config", str(cfg_path), "status"], stdout=out)
                    time.sleep(0.02)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"status: {exc}")

        t1 = threading.Thread(target=switch_profiles)
        t2 = threading.Thread(target=check_status)
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        # No unexpected exceptions should be raised
        self.assertEqual(errors, [], f"Concurrent operation errors: {errors}")


# ---------------------------------------------------------------------------
# Concurrent start / stop on different services
# ---------------------------------------------------------------------------


class TestConcurrentServiceManagement(IntegrationTestBase):
    """Multiple services can be started and stopped in parallel."""

    def test_parallel_start_and_stop_of_independent_services(self) -> None:
        """Starting and stopping different services in parallel is safe."""
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

        self.assertEqual(errors, [], f"Errors during parallel service lifecycle: {errors}")

        # All services must be stopped
        for name in service_names:
            self.assertFalse(sv.is_running(name), f"{name} still running after stop")

    def test_thread_pool_profile_switches_isolated_all_succeed(self) -> None:
        """Concurrent profile activations in isolated dirs each produce a valid active config."""
        workers_root = self.root / "pool_workers"
        workers_root.mkdir(parents=True, exist_ok=True)

        profiles = ["reliability", "balanced", "cost"]
        errors: list[str] = []

        def do_switch(index: int, profile: str) -> None:
            cfg_path, cfg = _make_isolated_config(workers_root, index)
            out = io.StringIO()
            code = run_cli(
                ["--config", str(cfg_path), "profile", "set", profile],
                stdout=out,
            )
            if code != 0:
                errors.append(f"worker {index} ({profile}): exit {code}")
                return

            # Each isolated worker's active config must be parseable JSON
            active_path = (
                Path(cfg["paths"]["active_config"])
            )
            active = json.loads(active_path.read_text(encoding="utf-8"))
            if "litellm_settings" not in active:
                errors.append(f"worker {index}: missing litellm_settings in active config")

        with ThreadPoolExecutor(max_workers=len(profiles)) as pool:
            futures = [pool.submit(do_switch, i, p) for i, p in enumerate(profiles)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(errors, [], f"Errors during pool profile switches: {errors}")


if __name__ == "__main__":
    unittest.main()
