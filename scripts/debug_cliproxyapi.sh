#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

show_help() {
    cat <<'HELP'
debug_cliproxyapi - CLIProxyAPIPlus 独立调试脚本

用法:
  ./scripts/debug_cliproxyapi.sh [start|stop] [config_path]
  ./scripts/debug_cliproxyapi.sh [config_path]

说明:
  启动或停止 cliproxyapi_plus 服务，并打印调试信息
  (配置路径、API keys、管理页面 URL 等)。

参数:
  start|stop              操作类型 (默认: start)
  config_path             配置文件路径 (默认: config/flowgate.yaml)

示例:
  ./scripts/debug_cliproxyapi.sh                          启动服务 (使用默认配置)
  ./scripts/debug_cliproxyapi.sh stop                     停止服务
  ./scripts/debug_cliproxyapi.sh start config/my.yaml     使用指定配置启动
  ./scripts/debug_cliproxyapi.sh config/my.yaml           同上 (省略 start)
HELP
}

. "$SCRIPT_DIR/_common.sh"
check_help "$@"

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
  show_help >&2
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
