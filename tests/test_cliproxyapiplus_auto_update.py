from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from flowgate.cliproxyapiplus import (
    check_latest_version,
    perform_update,
)


@pytest.mark.unit
def test_check_latest_version_returns_update_info():
    with mock.patch(
        "flowgate.cliproxyapiplus._http_get_json",
        return_value={
            "tag_name": "v6.8.18-1",
            "html_url": "https://github.com/example/releases/tag/v6.8.18-1",
        },
    ):
        result = check_latest_version("v6.8.16-0", "router-for-me/CLIProxyAPIPlus")

    assert result == {
        "current_version": "v6.8.16-0",
        "latest_version": "v6.8.18-1",
        "release_url": "https://github.com/example/releases/tag/v6.8.18-1",
    }


@pytest.mark.unit
def test_perform_update_restarts_running_service(tmp_path: Path):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "bin").mkdir(parents=True)

    config = {
        "paths": {
            "runtime_dir": str(runtime_dir),
            "log_file": str(tmp_path / "events.log"),
        },
        "services": {
            "cliproxyapi_plus": {
                "command": {
                    "args": ["CLIProxyAPIPlus", "-config", "config/cliproxyapi.yaml"],
                    "cwd": str(tmp_path),
                }
            }
        },
    }

    with (
        mock.patch(
            "flowgate.cliproxyapiplus.download_cliproxyapi_plus",
            return_value=runtime_dir / "bin" / "CLIProxyAPIPlus",
        ),
        mock.patch(
            "flowgate.cliproxyapiplus.validate_cliproxy_binary",
            return_value=True,
        ),
        mock.patch(
            "flowgate.cliproxyapiplus.write_installed_version"
        ) as write_ver,
        mock.patch(
            "flowgate.cliproxyapiplus.ProcessSupervisor"
        ) as supervisor_cls,
    ):
        supervisor = supervisor_cls.return_value
        supervisor.is_running.return_value = True
        supervisor.restart.return_value = 1234

        result = perform_update(
            config=config,
            latest_version="v6.8.18-1",
            repo="router-for-me/CLIProxyAPIPlus",
            require_sha256=False,
        )

    assert result["restarted_pid"] == 1234
    assert str(result["cliproxyapi_plus"]).endswith("/CLIProxyAPIPlus")
    write_ver.assert_called_once_with(str(runtime_dir), "v6.8.18-1")
