#!/usr/bin/env sh
set -eu

CONFIG_PATH="${1:-config/routertool.yaml}"
PROFILE="${PROFILE:-balanced}"
STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-45}"
POLL_INTERVAL="${POLL_INTERVAL:-2}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"

run_router() {
  uv run llm-router --config "$CONFIG_PATH" "$@"
}

print_port_hints() {
  if ! command -v lsof >/dev/null 2>&1; then
    echo "smoke: lsof not found, skip port diagnostics"
    return
  fi
  for port in 4000 8317; do
    echo "smoke: checking listeners on port $port"
    lsof -nP -iTCP:"$port" -sTCP:LISTEN || true
  done
}

cleanup() {
  run_router service stop all >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "smoke: [1/5] bootstrap runtime"
run_router bootstrap download

echo "smoke: [2/5] generate active profile ($PROFILE)"
run_router profile set "$PROFILE"

echo "smoke: [3/5] start services"
run_router service start all

echo "smoke: [4/5] wait for health readiness"
start_ts="$(date +%s)"
while true; do
  if run_router health; then
    break
  fi

  now_ts="$(date +%s)"
  elapsed="$((now_ts - start_ts))"
  if [ "$elapsed" -ge "$STARTUP_TIMEOUT" ]; then
    echo "smoke: health timeout after ${STARTUP_TIMEOUT}s"
    echo "smoke: status snapshot"
    run_router status || true
    print_port_hints
    exit 1
  fi

  sleep "$POLL_INTERVAL"
done

echo "smoke: [4.5/5] verify readiness endpoints"
endpoints="$({ uv run python - "$CONFIG_PATH" <<'PY'
from pathlib import Path
import json

from llm_router.config import load_router_config

cfg = load_router_config(Path(__import__('sys').argv[1]))
for service in cfg.get("services", {}).values():
    host = service.get("host", "127.0.0.1")
    port = service.get("port")
    if not isinstance(port, int):
        continue
    path = service.get("readiness_path") or service.get("health_path") or "/v1/models"
    print(f"http://{host}:{port}{path}")
PY
} | awk 'NF' )"

if command -v curl >/dev/null 2>&1; then
  echo "$endpoints" | while IFS= read -r url; do
    [ -z "$url" ] && continue
    curl --fail --silent --show-error --max-time 5 "$url" >/dev/null
    echo "smoke: readiness ok $url"
  done
else
  echo "smoke: curl not found, skip direct readiness endpoint checks"
fi

echo "smoke: [5/5] stop services"
run_router service stop all

echo "smoke: PASS"
