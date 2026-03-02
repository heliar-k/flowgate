import json
import tempfile
from pathlib import Path

import pytest

from flowgate.core.config import PathResolver, load_router_config


@pytest.mark.unit
def test_load_config_v3_derives_service_from_cliproxy_config():
    root = Path(tempfile.mkdtemp())
    cfg_dir = root / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    cliproxy_cfg = cfg_dir / "cliproxyapi.yaml"
    cliproxy_cfg.write_text(
        'host: "127.0.0.1"\n'
        "port: 8317\n"
        'api-keys: ["sk-local-test"]\n'
        "remote-management:\n"
        '  secret-key: "x"\n',
        encoding="utf-8",
    )

    flowgate_cfg = cfg_dir / "flowgate.yaml"
    flowgate_cfg.write_text(
        json.dumps(
            {
                "config_version": 3,
                "paths": {
                    # Intentionally relative to config dir
                    "runtime_dir": ".router/runtime",
                    "log_file": ".router/runtime/events.log",
                },
                # Intentionally relative to config dir
                "cliproxyapi_plus": {"config_file": "cliproxyapi.yaml"},
                "auth": {"providers": {"codex": {"method": "oauth_poll"}}},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_router_config(flowgate_cfg)
    assert loaded["config_version"] == 3

    assert "services" in loaded
    svc = loaded["services"]["cliproxyapi_plus"]
    assert svc["host"] == "127.0.0.1"
    assert svc["port"] == 8317
    assert svc["readiness_path"] == "/v1/models"
    assert "command" in svc and "args" in svc["command"]
    assert Path(svc["command"]["args"][0]).is_absolute()
    assert svc["command"]["args"][0].endswith("/.router/runtime/bin/CLIProxyAPIPlus")


@pytest.mark.unit
def test_path_resolver_resolves_cliproxyapi_plus_config_file():
    root = Path(tempfile.mkdtemp())
    cfg_dir = root / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    flowgate_cfg = cfg_dir / "flowgate.yaml"

    resolver = PathResolver(flowgate_cfg)
    resolved = resolver.resolve_config_paths(
        {
            "paths": {"runtime_dir": ".router/runtime", "log_file": "events.log"},
            "cliproxyapi_plus": {"config_file": "cliproxyapi.yaml"},
        }
    )
    assert resolved["cliproxyapi_plus"]["config_file"] == str(
        (cfg_dir / "cliproxyapi.yaml").resolve()
    )
