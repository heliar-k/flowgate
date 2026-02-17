from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


class ProcessSupervisor:
    def __init__(self, runtime_dir: str | Path):
        self.runtime_dir = Path(runtime_dir)
        self.pid_dir = self.runtime_dir / "pids"
        self.log_dir = self.runtime_dir / "process-logs"
        self.events_log = self.runtime_dir / "events.log"
        self._children: dict[str, subprocess.Popen[bytes]] = {}
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _pid_path(self, name: str) -> Path:
        return self.pid_dir / f"{name}.pid"

    def _read_pid(self, name: str) -> int | None:
        path = self._pid_path(name)
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    @staticmethod
    def _is_pid_running(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def record_event(
        self,
        event: str,
        *,
        service: str | None = None,
        profile: str | None = None,
        provider: str | None = None,
        result: str = "success",
        detail: str | None = None,
    ) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "service": service,
            "profile": profile,
            "provider": provider,
            "result": result,
            "detail": detail,
        }
        try:
            self.events_log.parent.mkdir(parents=True, exist_ok=True)
            with self.events_log.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except OSError:
            # Observability logging must never block service control path.
            return

    def is_running(self, name: str) -> bool:
        pid = self._read_pid(name)
        if pid is None:
            return False
        return self._is_pid_running(pid)

    def start(
        self,
        name: str,
        command: list[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> int:
        if self.is_running(name):
            pid = self._read_pid(name)
            if pid is None:
                raise RuntimeError(f"{name} appears running but no pid is available")
            self.record_event(
                "service_start",
                service=name,
                result="already-running",
                detail=f"pid={pid}",
            )
            return pid

        log_path = self.log_dir / f"{name}.log"
        log_file = log_path.open("ab")
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=run_env,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except Exception as exc:  # noqa: BLE001
            self.record_event(
                "service_start", service=name, result="failed", detail=str(exc)
            )
            log_file.close()
            raise

        self._pid_path(name).write_text(str(process.pid), encoding="utf-8")
        self._children[name] = process
        log_file.close()
        self.record_event(
            "service_start", service=name, result="success", detail=f"pid={process.pid}"
        )
        return process.pid

    def stop(self, name: str, *, timeout: float = 5.0) -> bool:
        child = self._children.get(name)
        if child is not None:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=1)
            self._pid_path(name).unlink(missing_ok=True)
            self._children.pop(name, None)
            self.record_event("service_stop", service=name, result="success")
            return True

        pid = self._read_pid(name)
        if pid is None:
            self.record_event("service_stop", service=name, result="not-running")
            return True

        if not self._is_pid_running(pid):
            self._pid_path(name).unlink(missing_ok=True)
            self.record_event(
                "service_stop", service=name, result="stale-pid", detail=f"pid={pid}"
            )
            return True

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            self._pid_path(name).unlink(missing_ok=True)
            self.record_event(
                "service_stop",
                service=name,
                result="already-exited",
                detail=f"pid={pid}",
            )
            return True

        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._is_pid_running(pid):
                self._pid_path(name).unlink(missing_ok=True)
                self.record_event(
                    "service_stop", service=name, result="success", detail=f"pid={pid}"
                )
                return True
            time.sleep(0.1)

        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

        for _ in range(10):
            if not self._is_pid_running(pid):
                self._pid_path(name).unlink(missing_ok=True)
                self.record_event(
                    "service_stop",
                    service=name,
                    result="success-after-kill",
                    detail=f"pid={pid}",
                )
                return True
            time.sleep(0.1)

        self.record_event(
            "service_stop", service=name, result="timeout", detail=f"pid={pid}"
        )
        return False

    def restart(
        self,
        name: str,
        command: list[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> int:
        stopped = self.stop(name)
        if not stopped:
            self.record_event(
                "service_restart", service=name, result="failed", detail="stop-timeout"
            )
            raise RuntimeError(f"Failed to stop service before restart: {name}")
        pid = self.start(name, command, cwd=cwd, env=env)
        self.record_event(
            "service_restart", service=name, result="success", detail=f"pid={pid}"
        )
        return pid
