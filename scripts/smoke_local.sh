#!/usr/bin/env sh
set -eu

CONFIG_PATH="${1:-config/flowgate.yaml}"
PROFILE="${PROFILE:-balanced}"
STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-45}"
POLL_INTERVAL="${POLL_INTERVAL:-2}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"

run_router() {
  uv run flowgate --config "$CONFIG_PATH" "$@"
}

upstream_api_key_file() {
  uv run python - "$CONFIG_PATH" <<'PY'
from pathlib import Path

from flowgate.cli.utils import _load_and_resolve_config

cfg = _load_and_resolve_config(__import__("sys").argv[1])
credentials = cfg.get("credentials", {})
upstream = credentials.get("upstream", {}) if isinstance(credentials, dict) else {}
entry = upstream.get("cliproxy_default", {}) if isinstance(upstream, dict) else {}
path = entry.get("file") if isinstance(entry, dict) else None
if isinstance(path, str) and path.strip():
    print(path)
PY
}

ensure_upstream_api_key_file() {
  key_file="$(upstream_api_key_file | awk 'NF' | head -n 1)"
  if [ -z "$key_file" ]; then
    echo "smoke: upstream credential path unresolved, skip api-key file auto-create"
    return
  fi

  if [ -s "$key_file" ]; then
    return
  fi

  key_value="${SMOKE_UPSTREAM_CLIPROXY_API_KEY:-sk-local-test}"
  mkdir -p "$(dirname "$key_file")"
  printf '%s\n' "$key_value" > "$key_file"
  chmod 600 "$key_file" || true
  echo "smoke: seeded upstream api key file: $key_file"
}

list_service_ports() {
  uv run python - "$CONFIG_PATH" <<'PY'
from pathlib import Path

from flowgate.config import load_router_config

cfg = load_router_config(Path(__import__("sys").argv[1]))
ports: set[int] = set()
for service in cfg.get("services", {}).values():
    port = service.get("port")
    if isinstance(port, int):
        ports.add(port)
for port in sorted(ports):
    print(port)
PY
}

list_readiness_endpoints() {
  uv run python - "$CONFIG_PATH" <<'PY'
from pathlib import Path

from flowgate.config import load_router_config
from flowgate.constants import DEFAULT_SERVICE_HOST, DEFAULT_READINESS_PATH

cfg = load_router_config(Path(__import__("sys").argv[1]))
for service in cfg.get("services", {}).values():
    host = service.get("host", DEFAULT_SERVICE_HOST)
    port = service.get("port")
    if not isinstance(port, int):
        continue
    path = service.get("readiness_path") or service.get("health_path") or DEFAULT_READINESS_PATH
    print(f"http://{host}:{port}{path}")
PY
}

litellm_base_url() {
  uv run python - "$CONFIG_PATH" <<'PY'
from pathlib import Path

from flowgate.config import load_router_config
from flowgate.constants import DEFAULT_SERVICE_HOST

cfg = load_router_config(Path(__import__("sys").argv[1]))
service = cfg.get("services", {}).get("litellm", {})
host = service.get("host", DEFAULT_SERVICE_HOST)
port = service.get("port")
if isinstance(port, int):
    print(f"http://{host}:{port}")
PY
}

print_port_hints() {
  if ! command -v lsof >/dev/null 2>&1; then
    echo "smoke: lsof not found, skip port diagnostics"
    return
  fi
  ports="$(list_service_ports | awk 'NF')"
  if [ -z "$ports" ]; then
    echo "smoke: no service ports resolved from config, skip port diagnostics"
    return
  fi
  echo "$ports" | while IFS= read -r port; do
    [ -z "$port" ] && continue
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

ensure_upstream_api_key_file

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
endpoints="$(list_readiness_endpoints | awk 'NF')"

if command -v curl >/dev/null 2>&1; then
  echo "$endpoints" | while IFS= read -r url; do
    [ -z "$url" ] && continue
    curl --fail --silent --show-error --max-time 5 "$url" >/dev/null
    echo "smoke: readiness ok $url"
  done
else
  echo "smoke: curl not found, skip direct readiness endpoint checks"
fi

echo "smoke: [4.6/6] probe Claude messages endpoint"
if command -v curl >/dev/null 2>&1; then
  litellm_base="$(litellm_base_url | awk 'NF' | head -n 1)"
  if [ -n "$litellm_base" ]; then
    probe_status="$(
      curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
        --max-time 5 \
        -X POST "$litellm_base/v1/messages/count_tokens" \
        -H "content-type: application/json" \
        -H "anthropic-version: 2023-06-01" \
        -H "authorization: Bearer sk-local-test" \
        -d '{"model":"router-default","messages":[{"role":"user","content":"ping"}]}'
    )"

    case "$probe_status" in
      2??|4??)
        if [ "$probe_status" = "404" ]; then
          echo "smoke: claude messages probe failed: status=$probe_status"
          exit 1
        fi
        echo "smoke: claude messages probe status=$probe_status"
        ;;
      *)
        echo "smoke: claude messages probe failed: status=$probe_status"
        exit 1
        ;;
    esac
  else
    echo "smoke: litellm base url unresolved, skip claude messages probe"
  fi
else
  echo "smoke: curl not found, skip claude messages probe"
fi

echo "smoke: [5/6] stop services"
run_router service stop all

echo "smoke: [6/6] PASS"
