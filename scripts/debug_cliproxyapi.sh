#!/usr/bin/env sh
set -eu

export UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"
export UV_TOOL_DIR="${UV_TOOL_DIR:-.uv-tools}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/debug_cliproxyapi.sh [start|stop] [config_path]
  ./scripts/debug_cliproxyapi.sh [config_path]

Control cliproxyapi_plus service for local debugging.
Defaults:
  action: start
  config_path: config/flowgate.yaml
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

ACTION="start"
CONFIG_PATH="config/flowgate.yaml"

if [ "$#" -ge 1 ]; then
  case "$1" in
    start|stop)
      ACTION="$1"
      shift
      ;;
    *)
      CONFIG_PATH="$1"
      shift
      ;;
  esac
fi

if [ "$#" -ge 1 ]; then
  CONFIG_PATH="$1"
  shift
fi

if [ "$#" -ne 0 ]; then
  usage >&2
  exit 2
fi

if [ ! -f "$CONFIG_PATH" ]; then
  echo "config not found: $CONFIG_PATH" >&2
  exit 2
fi

uv run python - "$CONFIG_PATH" <<'PY'
from __future__ import annotations

import os
from pathlib import Path

from flowgate.cliproxy_debug import (
    detect_cliproxy_config_path,
    management_api_url_from_auth,
    management_page_url,
    read_cliproxy_api_keys,
)
from flowgate.cli import _load_and_resolve_config

config_path = Path(os.sys.argv[1])
cfg = _load_and_resolve_config(str(config_path))
service = cfg["services"]["cliproxyapi_plus"]
host = str(service.get("host", "127.0.0.1"))
port = service.get("port", 8317)
cliproxy_cfg_path = detect_cliproxy_config_path(cfg, config_path)
api_keys = read_cliproxy_api_keys(cliproxy_cfg_path)
management_page = management_page_url(host, port)
management_api = management_api_url_from_auth(cfg, host, port)

print(f"cliproxyapi_config={cliproxy_cfg_path if cliproxy_cfg_path else 'n/a'}")
print(f"cliproxyapi_api_keys={','.join(api_keys) if api_keys else 'n/a'}")
print(f"cliproxyapi_management_url={management_page}")
print(f"cliproxyapi_management_api_url={management_api}")
PY

uv run flowgate --config "$CONFIG_PATH" service "$ACTION" cliproxyapi_plus
