from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any, Iterable, TextIO

from .auth_methods import get_headless_import_handler, headless_import_handlers
from .bootstrap import (
    DEFAULT_CLIPROXY_REPO,
    DEFAULT_CLIPROXY_VERSION,
    download_cliproxyapi_plus,
    prepare_litellm_runner,
    validate_cliproxy_binary,
    validate_litellm_runner,
)
from .cli.commands.health import DoctorCommand, HealthCommand, StatusCommand
from .cli.parser import build_parser
from .cli.utils import (
    _default_auth_dir,
    _load_and_resolve_config,
    _read_state_file,
    _resolve_config_paths,
    _resolve_path,
)
from .cliproxyapiplus_update_check import (
    check_cliproxyapiplus_update,
    read_cliproxyapiplus_installed_version,
    write_cliproxyapiplus_installed_version,
)
from .client_apply import apply_claude_code_settings, apply_codex_config
from .config import ConfigError, load_router_config
from .constants import (
    CLIPROXYAPI_PLUS_SERVICE,
    DEFAULT_READINESS_PATH,
    DEFAULT_SERVICE_HOST,
)
from .health import check_http_health
from .integration import build_integration_specs
from .oauth import fetch_auth_url, poll_auth_status
from .process import ProcessSupervisor
from .profile import activate_profile
from .security import check_secret_file_permissions


def _auth_providers(config: dict[str, Any]) -> dict[str, Any]:
    auth = config.get("auth", {})
    if isinstance(auth, dict):
        providers_raw = auth.get("providers", {})
        if isinstance(providers_raw, dict):
            return providers_raw

    oauth = config.get("oauth", {})
    if isinstance(oauth, dict):
        return oauth

    return {}


def _service_names(config: dict[str, Any], target: str) -> list[str]:
    if target == "all":
        return list(config["services"].keys())
    if target not in config["services"]:
        raise KeyError(f"Unknown service: {target}")
    return [target]


def _runtime_dependency_available(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:  # noqa: BLE001
        return False


def _is_service_port_available(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((host, port))
    except OSError:
        return False
    return True


def _upstream_credentials(config: dict[str, Any]) -> dict[str, str]:
    credentials = config.get("credentials", {})
    if not isinstance(credentials, dict):
        return {}

    upstream = credentials.get("upstream", {})
    if not isinstance(upstream, dict):
        return {}

    result: dict[str, str] = {}
    for name, entry in upstream.items():
        if not isinstance(name, str):
            continue
        if not isinstance(entry, dict):
            continue
        file_path = entry.get("file")
        if isinstance(file_path, str) and file_path.strip():
            result[name] = file_path
    return result


def _collect_api_key_refs(litellm_config: Any) -> set[str]:
    refs: set[str] = set()
    if not isinstance(litellm_config, dict):
        return refs

    model_list = litellm_config.get("model_list")
    if not isinstance(model_list, list):
        return refs

    for item in model_list:
        if not isinstance(item, dict):
            continue
        params = item.get("litellm_params")
        if not isinstance(params, dict):
            continue
        ref = params.get("api_key_ref")
        if isinstance(ref, str) and ref.strip():
            refs.add(ref.strip())
    return refs


def _upstream_credential_issues(config: dict[str, Any]) -> list[str]:
    refs = _collect_api_key_refs(config.get("litellm_base", {}))
    profiles = config.get("profiles", {})
    if isinstance(profiles, dict):
        for overlay in profiles.values():
            refs.update(_collect_api_key_refs(overlay))

    if not refs:
        return []

    upstream = _upstream_credentials(config)
    issues: list[str] = []
    for ref in sorted(refs):
        file_path = upstream.get(ref)
        if not file_path:
            issues.append(f"missing-ref:{ref}")
            continue

        key_path = Path(file_path)
        if not key_path.exists():
            issues.append(f"missing-file:{ref}:{key_path}")
            continue
        if not key_path.is_file():
            issues.append(f"not-a-file:{ref}:{key_path}")
            continue
        try:
            api_key = key_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            issues.append(f"read-error:{ref}:{type(exc).__name__}")
            continue
        if not api_key:
            issues.append(f"empty-file:{ref}:{key_path}")
            continue

    return issues


def _is_executable_file(path: Path) -> bool:
    return path.exists() and path.is_file() and os.access(path, os.X_OK)


def _cmd_profile_list(config: dict[str, Any], *, stdout: TextIO) -> int:
    for name in sorted(config["profiles"].keys()):
        print(name, file=stdout)
    return 0


def _cmd_profile_set(
    config: dict[str, Any], profile: str, *, stdout: TextIO, stderr: TextIO
) -> int:
    try:
        active_path, state_path = activate_profile(config, profile)
    except KeyError as exc:
        print(str(exc), file=stderr)
        return 2

    supervisor = ProcessSupervisor(config["paths"]["runtime_dir"])
    supervisor.record_event("profile_switch", profile=profile, result="success")

    print(f"profile={profile}", file=stdout)
    print(f"active_config={active_path}", file=stdout)
    print(f"state_file={state_path}", file=stdout)

    # If LiteLLM is already running, apply the profile switch immediately by restart.
    if "litellm" in config["services"] and supervisor.is_running("litellm"):
        service = config["services"]["litellm"]
        command = service["command"]["args"]
        cwd = service["command"].get("cwd") or os.getcwd()
        pid = supervisor.restart("litellm", command, cwd=cwd)
        print(f"litellm:restarted pid={pid}", file=stdout)
    return 0




def _cmd_auth_login(
    config: dict[str, Any],
    provider: str,
    *,
    timeout: float,
    poll_interval: float,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    supervisor = ProcessSupervisor(config["paths"]["runtime_dir"])
    providers = _auth_providers(config)
    if provider not in providers:
        supervisor.record_event(
            "oauth_login",
            provider=provider,
            result="failed",
            detail="provider-not-configured",
        )
        available = ",".join(sorted(str(k) for k in providers.keys())) or "none"
        print(
            f"OAuth provider not configured: {provider}; available={available}",
            file=stderr,
        )
        return 2

    provider_cfg = providers[provider]
    auth_url_endpoint = provider_cfg.get("auth_url_endpoint")
    status_endpoint = provider_cfg.get("status_endpoint")
    if not auth_url_endpoint or not status_endpoint:
        supervisor.record_event(
            "oauth_login", provider=provider, result="failed", detail="endpoint-missing"
        )
        print(f"OAuth endpoints not complete for provider={provider}", file=stderr)
        return 2

    try:
        url = fetch_auth_url(auth_url_endpoint, timeout=5)
        print(f"login_url={url}", file=stdout)
        status = poll_auth_status(
            status_endpoint,
            timeout_seconds=timeout,
            poll_interval_seconds=poll_interval,
        )
        supervisor.record_event("oauth_login", provider=provider, result="success")
        print(f"oauth_status={status}", file=stdout)
        return 0
    except Exception as exc:  # noqa: BLE001
        supervisor.record_event(
            "oauth_login", provider=provider, result="failed", detail=str(exc)
        )
        print(
            (
                f"OAuth login failed: {exc} "
                "hint=verify auth endpoints, run `auth status`, then retry with a larger --timeout if needed"
            ),
            file=stderr,
        )
        return 1


def _cmd_auth_list(config: dict[str, Any], *, stdout: TextIO) -> int:
    providers_map = _auth_providers(config)
    providers = sorted(str(name) for name in providers_map.keys())
    handlers = headless_import_handlers()

    if not providers:
        print("oauth_providers=none", file=stdout)
        print("headless_import_providers=none", file=stdout)
        return 0

    for provider in providers:
        provider_cfg = providers_map.get(provider, {})
        oauth_supported = bool(
            isinstance(provider_cfg, dict)
            and provider_cfg.get("auth_url_endpoint")
            and provider_cfg.get("status_endpoint")
        )
        headless = "yes" if provider in handlers else "no"
        print(
            f"provider={provider} oauth_login={'yes' if oauth_supported else 'no'} headless_import={headless}",
            file=stdout,
        )

    supported = sorted(provider for provider in providers if provider in handlers)
    print(f"oauth_providers={','.join(providers)}", file=stdout)
    print(
        f"headless_import_providers={','.join(supported) if supported else 'none'}",
        file=stdout,
    )
    return 0


def _cmd_auth_status(config: dict[str, Any], *, stdout: TextIO) -> int:
    providers_map = _auth_providers(config)
    providers = sorted(str(name) for name in providers_map.keys())
    handlers = headless_import_handlers()

    print(f"default_auth_dir={_default_auth_dir(config)}", file=stdout)
    issues = check_secret_file_permissions(_effective_secret_files(config))
    print(f"secret_permission_issues={len(issues)}", file=stdout)

    if not providers:
        print("providers=none", file=stdout)
        return 0

    for provider in providers:
        provider_cfg = providers_map.get(provider, {})
        method = "unknown"
        oauth_supported = False
        if isinstance(provider_cfg, dict):
            method = str(provider_cfg.get("method", "oauth_poll"))
            oauth_supported = bool(
                provider_cfg.get("auth_url_endpoint")
                and provider_cfg.get("status_endpoint")
            )
        print(
            (
                f"provider={provider} "
                f"method={method} "
                f"oauth_login={'yes' if oauth_supported else 'no'} "
                f"headless_import={'yes' if provider in handlers else 'no'}"
            ),
            file=stdout,
        )

    return 0


def _cmd_auth_import_headless(
    config: dict[str, Any],
    provider: str,
    *,
    source: str,
    dest_dir: str | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    handler = get_headless_import_handler(provider)
    if handler is None:
        supported = ",".join(sorted(headless_import_handlers().keys())) or "none"
        print(
            f"headless import not supported for provider={provider}; supported={supported}",
            file=stderr,
        )
        return 2

    resolved_dest = dest_dir
    if not resolved_dest:
        resolved_dest = _default_auth_dir(config)

    try:
        saved = handler(source, resolved_dest)
    except Exception as exc:  # noqa: BLE001
        print(f"headless import failed: {exc}", file=stderr)
        return 1

    supervisor = ProcessSupervisor(config["paths"]["runtime_dir"])
    supervisor.record_event(
        "auth_import",
        provider=provider,
        result="success",
        detail=f"method=headless path={saved}",
    )
    print(f"saved_auth={saved}", file=stdout)
    return 0


def _cmd_auth_codex_import_headless(
    config: dict[str, Any],
    *,
    source: str,
    dest_dir: str | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    return _cmd_auth_import_headless(
        config,
        "codex",
        source=source,
        dest_dir=dest_dir,
        stdout=stdout,
        stderr=stderr,
    )


def _cmd_service_action(
    config: dict[str, Any], action: str, target: str, *, stdout: TextIO, stderr: TextIO
) -> int:
    supervisor = ProcessSupervisor(config["paths"]["runtime_dir"])
    try:
        names = _service_names(config, target)
    except KeyError as exc:
        print(str(exc), file=stderr)
        return 2

    ok = True
    started_cliproxy = False
    for name in names:
        service = config["services"][name]
        args = service["command"]["args"]
        cwd = service["command"].get("cwd")
        host = str(service.get("host", DEFAULT_SERVICE_HOST))
        port = service.get("port")
        if cwd is None:
            cwd = os.getcwd()

        if action in {"start", "restart"} and isinstance(port, int):
            running = supervisor.is_running(name)
            should_check_port = action == "start" and not running
            should_check_port = should_check_port or (
                action == "restart" and not running
            )
            if should_check_port and not _is_service_port_available(host, port):
                ok = False
                print(
                    f"{name}:{action}-failed reason=port-in-use host={host} port={port}",
                    file=stderr,
                )
                continue

        if action == "start":
            pid = supervisor.start(name, args, cwd=cwd)
            print(f"{name}:started pid={pid}", file=stdout)
            if name == CLIPROXYAPI_PLUS_SERVICE:
                started_cliproxy = True
        elif action == "stop":
            stopped = supervisor.stop(name)
            print(f"{name}:{'stopped' if stopped else 'stop-failed'}", file=stdout)
            ok = ok and stopped
        elif action == "restart":
            pid = supervisor.restart(name, args, cwd=cwd)
            print(f"{name}:restarted pid={pid}", file=stdout)
        else:
            print(f"Unsupported action: {action}", file=stderr)
            return 2

    if action == "start" and started_cliproxy:
        _maybe_print_cliproxyapiplus_update(config, stdout=stdout)

    return 0 if ok else 1


def _cmd_bootstrap_download(
    config: dict[str, Any],
    *,
    cliproxy_version: str,
    cliproxy_repo: str,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    runtime_bin_dir = Path(config["paths"]["runtime_dir"]) / "bin"
    try:
        cliproxy = download_cliproxyapi_plus(
            runtime_bin_dir,
            version=cliproxy_version,
            repo=cliproxy_repo,
        )
        litellm = prepare_litellm_runner(runtime_bin_dir)
        if not validate_cliproxy_binary(cliproxy):
            raise RuntimeError(f"Invalid CLIProxyAPIPlus binary downloaded: {cliproxy}")
        if not validate_litellm_runner(litellm):
            raise RuntimeError(f"Invalid litellm runner generated: {litellm}")
    except Exception as exc:  # noqa: BLE001
        print(f"bootstrap failed: {exc}", file=stderr)
        return 1

    write_cliproxyapiplus_installed_version(
        config["paths"]["runtime_dir"], cliproxy_version
    )
    print(f"cliproxyapi_plus={cliproxy}", file=stdout)
    print(f"litellm={litellm}", file=stdout)
    return 0




def _maybe_print_cliproxyapiplus_update(
    config: dict[str, Any], *, stdout: TextIO
) -> None:
    isatty = getattr(stdout, "isatty", None)
    if callable(isatty) and not isatty():
        return

    runtime_dir = str(config.get("paths", {}).get("runtime_dir", "")).strip()
    if not runtime_dir:
        return

    current_version = read_cliproxyapiplus_installed_version(
        runtime_dir, DEFAULT_CLIPROXY_VERSION
    )
    update = check_cliproxyapiplus_update(
        runtime_dir=runtime_dir,
        current_version=current_version,
        repo=DEFAULT_CLIPROXY_REPO,
    )
    if not update:
        return

    latest = update["latest_version"]
    release_url = update.get("release_url", "")
    config_path = str(
        config.get("_meta", {}).get("config_path", "config/flowgate.yaml")
    )
    print(
        (
            "cliproxyapi_plus:update_available "
            f"current={current_version} latest={latest} "
            f"release={release_url if release_url else 'n/a'}"
        ),
        file=stdout,
    )
    print(
        (
            "cliproxyapi_plus:update_suggestion "
            "command="
            f"'uv run flowgate --config {config_path} "
            f"bootstrap download --cliproxy-version {latest}'"
        ),
        file=stdout,
    )


def _render_codex_integration(spec: dict[str, Any]) -> str:
    base_url = str(spec.get("base_url", "")).strip()
    model = str(spec.get("model", "router-default")).strip() or "router-default"
    return "\n".join(
        [
            'model_provider = "flowgate"',
            f'model = "{model}"',
            "",
            "[model_providers.flowgate]",
            'name = "FlowGate Local"',
            f'base_url = "{base_url}"',
            'env_key = "OPENAI_API_KEY"',
            'wire_api = "responses"',
        ]
    )


def _render_claude_code_integration(spec: dict[str, Any]) -> str:
    base_url = str(spec.get("base_url", "")).strip()
    env = spec.get("env", {})
    if not isinstance(env, dict):
        env = {}

    lines = [
        f"ANTHROPIC_BASE_URL={base_url}",
        "ANTHROPIC_AUTH_TOKEN=your-gateway-token",
    ]
    for key in (
        "ANTHROPIC_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    ):
        value = str(env.get(key, "")).strip()
        if value:
            lines.append(f"{key}={value}")
    return "\n".join(lines)


def _cmd_integration_print(
    config: dict[str, Any], client: str, *, stdout: TextIO, stderr: TextIO
) -> int:
    try:
        specs = build_integration_specs(config)
    except Exception as exc:  # noqa: BLE001
        print(f"integration render failed: {exc}", file=stderr)
        return 1

    if client == "codex":
        print(_render_codex_integration(specs.get("codex", {})), file=stdout)
        return 0
    if client == "claude-code":
        print(
            _render_claude_code_integration(specs.get("claude_code", {})), file=stdout
        )
        return 0

    print(f"Unknown integration client: {client}", file=stderr)
    return 2


def _cmd_integration_apply(
    config: dict[str, Any],
    client: str,
    *,
    target: str | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    try:
        specs = build_integration_specs(config)
    except Exception as exc:  # noqa: BLE001
        print(f"integration render failed: {exc}", file=stderr)
        return 1

    if client == "codex":
        resolved_target = target or "~/.codex/config.toml"
        spec = specs.get("codex", {})
        if not isinstance(spec, dict):
            print("integration spec missing codex block", file=stderr)
            return 1
        try:
            result = apply_codex_config(resolved_target, spec)
        except Exception as exc:  # noqa: BLE001
            print(f"integration apply failed: {exc}", file=stderr)
            return 1
    elif client == "claude-code":
        resolved_target = target or "~/.claude/settings.json"
        spec = specs.get("claude_code", {})
        if not isinstance(spec, dict):
            print("integration spec missing claude_code block", file=stderr)
            return 1
        try:
            result = apply_claude_code_settings(resolved_target, spec)
        except Exception as exc:  # noqa: BLE001
            print(f"integration apply failed: {exc}", file=stderr)
            return 1
    else:
        print(f"Unknown integration client: {client}", file=stderr)
        return 2

    print(f"saved_path={result['path']}", file=stdout)
    backup_path = result.get("backup_path")
    if backup_path:
        print(f"backup_path={backup_path}", file=stdout)
    return 0


# Command routing map for new command structure
COMMAND_MAP = {
    "status": StatusCommand,
    "health": HealthCommand,
    "doctor": DoctorCommand,
}


def run_cli(
    argv: Iterable[str], *, stdout: TextIO | None = None, stderr: TextIO | None = None
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()

    try:
        args = parser.parse_args(list(argv))
        config = _load_and_resolve_config(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"Config file not found: {exc}", file=stderr)
        return 2

    # Route to new command structure if available
    if args.command in COMMAND_MAP:
        # Inject stdout/stderr into args for command access
        args.stdout = stdout
        args.stderr = stderr
        command_class = COMMAND_MAP[args.command]
        command = command_class(args, config)
        return command.execute()

    if args.command == "profile":
        if args.profile_cmd == "list":
            return _cmd_profile_list(config, stdout=stdout)
        if args.profile_cmd == "set":
            return _cmd_profile_set(config, args.name, stdout=stdout, stderr=stderr)

    if args.command == "integration":
        if args.integration_cmd == "print":
            return _cmd_integration_print(
                config,
                args.client,
                stdout=stdout,
                stderr=stderr,
            )
        if args.integration_cmd == "apply":
            return _cmd_integration_apply(
                config,
                args.client,
                target=args.target if args.target else None,
                stdout=stdout,
                stderr=stderr,
            )

    if args.command == "auth":
        if args.provider == "list":
            return _cmd_auth_list(config, stdout=stdout)
        if args.provider == "status":
            return _cmd_auth_status(config, stdout=stdout)
        if args.provider == "login":
            return _cmd_auth_login(
                config,
                args.login_provider,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                stdout=stdout,
                stderr=stderr,
            )
        if args.provider == "import-headless":
            return _cmd_auth_import_headless(
                config,
                args.import_provider,
                source=args.source,
                dest_dir=args.dest_dir if args.dest_dir else None,
                stdout=stdout,
                stderr=stderr,
            )
        if args.auth_cmd == "login":
            return _cmd_auth_login(
                config,
                args.provider,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                stdout=stdout,
                stderr=stderr,
            )
        if args.provider == "codex" and args.auth_cmd == "import-headless":
            return _cmd_auth_codex_import_headless(
                config,
                source=args.source,
                dest_dir=args.dest_dir if args.dest_dir else None,
                stdout=stdout,
                stderr=stderr,
            )

    if args.command == "service":
        return _cmd_service_action(
            config,
            args.service_cmd,
            args.target,
            stdout=stdout,
            stderr=stderr,
        )

    if args.command == "bootstrap":
        if args.bootstrap_cmd == "download":
            return _cmd_bootstrap_download(
                config,
                cliproxy_version=args.cliproxy_version,
                cliproxy_repo=args.cliproxy_repo,
                stdout=stdout,
                stderr=stderr,
            )

    print("Unknown command", file=stderr)
    return 2
