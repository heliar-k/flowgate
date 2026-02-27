#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

show_help() {
    cat <<'HELP'
smoke_local - FlowGate 端到端冒烟测试 (v3, cliproxy-only)

用法:
  ./scripts/smoke_local.sh [config_path]

说明:
  执行完整的端到端冒烟测试流程:
    1. 下载运行时二进制文件 (bootstrap download)
    2. 启动服务 (service start all)
    3. 等待 /v1/models 就绪
    4. 停止服务 (service stop all)

参数:
  config_path             配置文件路径 (默认: config/flowgate.yaml)

环境变量:
  STARTUP_TIMEOUT         启动超时秒数 (默认: 45)
  POLL_INTERVAL           轮询间隔秒数 (默认: 2)
  SMOKE_CLIENT_API_KEY    用于访问本地代理的 client api key
                          (默认: cliproxyapi.yaml 中第一个 api-keys)
  SMOKE_UPSTREAM_CLIPROXY_API_KEY
                          兼容旧变量名 (等价于 SMOKE_CLIENT_API_KEY)

示例:
  ./scripts/smoke_local.sh
  ./scripts/smoke_local.sh config/flowgate.yaml
  STARTUP_TIMEOUT=60 ./scripts/smoke_local.sh
HELP
}

. "$SCRIPT_DIR/_common.sh"
check_help "$@"

CONFIG_PATH="${1:-config/flowgate.yaml}"
STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-45}"
POLL_INTERVAL="${POLL_INTERVAL:-2}"

run_router() {
  uv run flowgate --config "$CONFIG_PATH" "$@"
}

# Backward-compatibility shim for older smoke scripts/tests.
# v3 no longer seeds upstream key files; client auth is configured in cliproxyapi.yaml `api-keys`.
ensure_upstream_api_key_file() {
  return 0
}

cliproxy_models_url() {
  uv run python - "$CONFIG_PATH" <<'PY'
from pathlib import Path

from flowgate.config import load_router_config
from flowgate.constants import DEFAULT_SERVICE_HOST, DEFAULT_READINESS_PATH

cfg = load_router_config(Path(__import__("sys").argv[1]))
service = cfg.get("services", {}).get("cliproxyapi_plus", {})
host = service.get("host") or DEFAULT_SERVICE_HOST
port = service.get("port")
path = service.get("readiness_path") or DEFAULT_READINESS_PATH
if isinstance(port, int):
    print(f"http://{host}:{port}{path}")
PY
}

cliproxy_base_url() {
  uv run python - "$CONFIG_PATH" <<'PY'
from pathlib import Path

from flowgate.config import load_router_config
from flowgate.constants import DEFAULT_SERVICE_HOST

cfg = load_router_config(Path(__import__("sys").argv[1]))
service = cfg.get("services", {}).get("cliproxyapi_plus", {})
host = service.get("host") or DEFAULT_SERVICE_HOST
port = service.get("port")
if isinstance(port, int):
    print(f"http://{host}:{port}")
PY
}

cliproxy_api_key() {
  uv run python - "$CONFIG_PATH" <<'PY'
import json
from pathlib import Path

from flowgate.config import load_router_config

cfg_path = Path(__import__("sys").argv[1])
flow = load_router_config(cfg_path)
cliproxy_cfg_path = Path(flow.get("cliproxyapi_plus", {}).get("config_file", ""))
if not cliproxy_cfg_path:
    raise SystemExit(1)
text = cliproxy_cfg_path.read_text(encoding="utf-8")
try:
    import yaml  # type: ignore
    data = yaml.safe_load(text)
except ModuleNotFoundError:
    data = json.loads(text)
keys = (data or {}).get("api-keys") if isinstance(data, dict) else None
if isinstance(keys, list) and keys and isinstance(keys[0], str) and keys[0].strip():
    print(keys[0].strip())
PY
}

stop_services() {
  run_router service stop all || true
}

trap stop_services EXIT INT TERM

echo "smoke: [1/4] bootstrap download"
run_router bootstrap download

echo "smoke: [2/4] service start all"
run_router service start all

url="$(cliproxy_models_url | awk 'NF' | head -n 1)"
if [ -z "$url" ]; then
  echo "smoke: failed to derive /v1/models url"
  exit 1
fi

api_key="${SMOKE_CLIENT_API_KEY:-${SMOKE_UPSTREAM_CLIPROXY_API_KEY:-}}"
if [ -z "$api_key" ]; then
  api_key="$(cliproxy_api_key | awk 'NF' | head -n 1 || true)"
fi

echo "smoke: [3/4] wait readiness url=$url"

deadline=$(( $(date +%s) + STARTUP_TIMEOUT ))
while :; do
  now="$(date +%s)"
  if [ "$now" -ge "$deadline" ]; then
    echo "smoke: timeout waiting for readiness"
    exit 1
  fi

  if [ -n "$api_key" ]; then
    if curl --silent --show-error --fail -H "Authorization: Bearer $api_key" "$url" >/dev/null; then
      break
    fi
  else
    if curl --silent --show-error --fail "$url" >/dev/null; then
      break
    fi
  fi

  sleep "$POLL_INTERVAL"
done

echo "smoke: readiness ok"

base_url="$(cliproxy_base_url | awk 'NF' | head -n 1)"
if [ -n "$base_url" ]; then
  echo "smoke: probe claude count_tokens"
  probe_url="$base_url/v1/messages/count_tokens"
  payload='{"model":"claude-sonnet","messages":[{"role":"user","content":"ping"}]}'
  if [ -n "$api_key" ]; then
    curl --silent --show-error --fail \
      -H "Authorization: Bearer $api_key" \
      -H "anthropic-version: 2023-06-01" \
      -H "Content-Type: application/json" \
      -X POST "$probe_url" \
      -d "$payload" >/dev/null || true
  else
    curl --silent --show-error --fail \
      -H "anthropic-version: 2023-06-01" \
      -H "Content-Type: application/json" \
      -X POST "$probe_url" \
      -d "$payload" >/dev/null || true
  fi
fi

echo "smoke: [4/4] service stop all"
run_router service stop all
