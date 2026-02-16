from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Mapping


class ProcessSupervisor:
    def __init__(self, runtime_dir: str | Path):
        self.runtime_dir = Path(runtime_dir)
        self.pid_dir = self.runtime_dir / "pids"
        self.log_dir = self.runtime_dir / "process-logs"
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
            return pid

        log_path = self.log_dir / f"{name}.log"
        log_file = log_path.open("ab")
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=run_env,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self._pid_path(name).write_text(str(process.pid), encoding="utf-8")
        self._children[name] = process
        log_file.close()
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
            return True

        pid = self._read_pid(name)
        if pid is None:
            return True

        if not self._is_pid_running(pid):
            self._pid_path(name).unlink(missing_ok=True)
            return True

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            self._pid_path(name).unlink(missing_ok=True)
            return True

        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._is_pid_running(pid):
                self._pid_path(name).unlink(missing_ok=True)
                return True
            time.sleep(0.1)

        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

        for _ in range(10):
            if not self._is_pid_running(pid):
                self._pid_path(name).unlink(missing_ok=True)
                return True
            time.sleep(0.1)

        return False

    def restart(
        self,
        name: str,
        command: list[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> int:
        self.stop(name)
        return self.start(name, command, cwd=cwd, env=env)
