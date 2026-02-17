from __future__ import annotations

import argparse
import json
import os
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
from .config import ConfigError, load_router_config
from .constants import DEFAULT_READINESS_PATH, DEFAULT_SERVICE_HOST
from .health import check_http_health
from .oauth import fetch_auth_url, poll_auth_status
from .process import ProcessSupervisor
from .profile import activate_profile
from .security import check_secret_file_permissions


def _resolve_path(base_dir: Path, value: str) -> str:
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str((base_dir / p).resolve())


def _resolve_config_paths(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    cfg = json.loads(json.dumps(config))
    base_dir = config_path.parent

    for key, value in cfg["paths"].items():
        if isinstance(value, str):
            cfg["paths"][key] = _resolve_path(base_dir, value)

    cfg["secret_files"] = [
        _resolve_path(base_dir, p) for p in cfg.get("secret_files", [])
    ]

    for service in cfg.get("services", {}).values():
        command = service.get("command", {})
        cwd = command.get("cwd")
        if isinstance(cwd, str):
            command["cwd"] = _resolve_path(base_dir, cwd)

    return cfg


def _load_and_resolve_config(path: str) -> dict[str, Any]:
    cfg_path = Path(path)
    cfg = load_router_config(cfg_path)
    resolved = _resolve_config_paths(cfg, cfg_path)
    resolved["_meta"] = {
        "config_path": str(cfg_path.resolve()),
        "config_dir": str(cfg_path.resolve().parent),
    }
    return resolved


def _read_state_file(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _default_auth_dir(config: dict[str, Any]) -> str:
    runtime_dir = config.get("paths", {}).get("runtime_dir")
    if isinstance(runtime_dir, str) and runtime_dir:
        return str((Path(runtime_dir).resolve().parent / "auths").resolve())

    config_dir = Path(config.get("_meta", {}).get("config_dir", os.getcwd()))
    return str((config_dir / "auths").resolve())


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


def _effective_secret_files(config: dict[str, Any]) -> list[str]:
    paths: set[str] = set()
    for value in config.get("secret_files", []):
        if isinstance(value, str) and value.strip():
            paths.add(str(Path(value).resolve()))

    default_auth_dir = Path(_default_auth_dir(config))
    if default_auth_dir.exists():
        for item in default_auth_dir.glob("*.json"):
            paths.add(str(item.resolve()))

    return sorted(paths)


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


def _cmd_status(config: dict[str, Any], *, stdout: TextIO) -> int:
    state = _read_state_file(Path(config["paths"]["state_file"]))
    profile = state.get("current_profile", "unknown")
    updated_at = state.get("updated_at", "unknown")

    print(f"current_profile={profile}", file=stdout)
    print(f"updated_at={updated_at}", file=stdout)

    supervisor = ProcessSupervisor(config["paths"]["runtime_dir"])
    for name in sorted(config["services"].keys()):
        running = supervisor.is_running(name)
        print(f"{name}_running={'yes' if running else 'no'}", file=stdout)

    issues = check_secret_file_permissions(_effective_secret_files(config))
    if issues:
        print(f"secret_permission_issues={len(issues)}", file=stdout)
    else:
        print("secret_permission_issues=0", file=stdout)

    return 0


def _cmd_health(config: dict[str, Any], *, stdout: TextIO) -> int:
    supervisor = ProcessSupervisor(config["paths"]["runtime_dir"])
    all_ok = True
    for name, service in sorted(config["services"].items()):
        running = supervisor.is_running(name)
        liveness_ok = running

        host = service.get("host", DEFAULT_SERVICE_HOST)
        port = service.get("port")
        readiness_path = (
            service.get("readiness_path")
            or service.get("health_path")
            or DEFAULT_READINESS_PATH
        )

        if isinstance(port, int):
            readiness_url = f"http://{host}:{port}{readiness_path}"
            readiness = check_http_health(readiness_url, timeout=1.0)
        else:
            readiness_url = "n/a"
            readiness = {"ok": False, "status_code": None, "error": "missing-port"}

        readiness_ok = bool(readiness["ok"])
        code = readiness["status_code"]
        error = readiness["error"]
        print(
            (
                f"{name}:liveness={'ok' if liveness_ok else 'fail'} "
                f"readiness={'ok' if readiness_ok else 'fail'} "
                f"running={'yes' if running else 'no'} "
                f"readiness_code={code if code is not None else 'n/a'} "
                f"readiness_error={error or 'none'} "
                f"readiness_url={readiness_url}"
            ),
            file=stdout,
        )

        all_ok = all_ok and liveness_ok and readiness_ok
    return 0 if all_ok else 1


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
    for name in names:
        service = config["services"][name]
        args = service["command"]["args"]
        cwd = service["command"].get("cwd")
        if cwd is None:
            cwd = os.getcwd()

        if action == "start":
            pid = supervisor.start(name, args, cwd=cwd)
            print(f"{name}:started pid={pid}", file=stdout)
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

    print(f"cliproxyapi_plus={cliproxy}", file=stdout)
    print(f"litellm={litellm}", file=stdout)
    return 0


def _cmd_doctor(config: dict[str, Any], *, stdout: TextIO) -> int:
    all_ok = True

    config_path = config.get("_meta", {}).get("config_path", "unknown")
    print(f"doctor:config=pass path={config_path}", file=stdout)

    runtime_dir = Path(config["paths"]["runtime_dir"])
    if runtime_dir.exists():
        print(f"doctor:runtime_dir=pass path={runtime_dir}", file=stdout)
    else:
        all_ok = False
        print(
            "doctor:runtime_dir=fail "
            f"path={runtime_dir} "
            "suggestion='run bootstrap download to create runtime artifacts'",
            file=stdout,
        )

    runtime_bin = runtime_dir / "bin"
    required_bins = {
        "CLIProxyAPIPlus": runtime_bin / "CLIProxyAPIPlus",
        "litellm": runtime_bin / "litellm",
    }
    missing_or_non_exec = [
        name
        for name, binary_path in required_bins.items()
        if not _is_executable_file(binary_path)
    ]
    if missing_or_non_exec:
        all_ok = False
        print(
            "doctor:runtime_binaries=fail "
            f"missing={','.join(missing_or_non_exec)} "
            "suggestion='uv run flowgate --config config/flowgate.yaml bootstrap download'",
            file=stdout,
        )
    else:
        print(f"doctor:runtime_binaries=pass path={runtime_bin}", file=stdout)

    issues = check_secret_file_permissions(_effective_secret_files(config))
    if issues:
        all_ok = False
        print(
            "doctor:secret_permissions=fail "
            f"issues={len(issues)} "
            "suggestion='chmod 600 <secret-file>'",
            file=stdout,
        )
    else:
        print("doctor:secret_permissions=pass issues=0", file=stdout)

    if _runtime_dependency_available("litellm"):
        print("doctor:runtime_dependency=pass module=litellm", file=stdout)
    else:
        all_ok = False
        print(
            "doctor:runtime_dependency=fail "
            "module=litellm "
            "suggestion='uv sync --group runtime'",
            file=stdout,
        )

    return 0 if all_ok else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flowgate")
    parser.add_argument("--config", default="config/flowgate.yaml")

    sub = parser.add_subparsers(dest="command", required=True)

    profile = sub.add_parser("profile")
    profile_sub = profile.add_subparsers(dest="profile_cmd", required=True)
    profile_sub.add_parser("list")
    p_set = profile_sub.add_parser("set")
    p_set.add_argument("name")

    sub.add_parser("status")
    sub.add_parser("health")
    sub.add_parser("doctor")

    auth = sub.add_parser("auth")
    auth_sub = auth.add_subparsers(dest="provider", required=True)
    auth_sub.add_parser("list")
    auth_sub.add_parser("status")

    login_any = auth_sub.add_parser("login")
    login_any.add_argument("login_provider")
    login_any.add_argument("--timeout", type=float, default=120)
    login_any.add_argument("--poll-interval", type=float, default=2)

    import_headless_any = auth_sub.add_parser("import-headless")
    import_headless_any.add_argument("import_provider")
    import_headless_any.add_argument("--source", default="~/.codex/auth.json")
    import_headless_any.add_argument("--dest-dir", default="")

    for provider in ("codex", "copilot"):
        provider_parser = auth_sub.add_parser(provider)
        provider_sub = provider_parser.add_subparsers(dest="auth_cmd", required=True)
        login = provider_sub.add_parser("login")
        login.add_argument("--timeout", type=float, default=120)
        login.add_argument("--poll-interval", type=float, default=2)
        if provider == "codex":
            import_headless = provider_sub.add_parser("import-headless")
            import_headless.add_argument("--source", default="~/.codex/auth.json")
            import_headless.add_argument("--dest-dir", default="")

    service = sub.add_parser("service")
    service_sub = service.add_subparsers(dest="service_cmd", required=True)
    for action in ("start", "stop", "restart"):
        action_parser = service_sub.add_parser(action)
        action_parser.add_argument("target", nargs="?", default="all")

    bootstrap = sub.add_parser("bootstrap")
    bootstrap_sub = bootstrap.add_subparsers(dest="bootstrap_cmd", required=True)
    download = bootstrap_sub.add_parser("download")
    download.add_argument("--cliproxy-version", default=DEFAULT_CLIPROXY_VERSION)
    download.add_argument("--cliproxy-repo", default=DEFAULT_CLIPROXY_REPO)

    return parser


def run_cli(
    argv: Iterable[str], *, stdout: TextIO | None = None, stderr: TextIO | None = None
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = _build_parser()

    try:
        args = parser.parse_args(list(argv))
        config = _load_and_resolve_config(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"Config file not found: {exc}", file=stderr)
        return 2

    if args.command == "profile":
        if args.profile_cmd == "list":
            return _cmd_profile_list(config, stdout=stdout)
        if args.profile_cmd == "set":
            return _cmd_profile_set(config, args.name, stdout=stdout, stderr=stderr)

    if args.command == "status":
        return _cmd_status(config, stdout=stdout)

    if args.command == "health":
        return _cmd_health(config, stdout=stdout)

    if args.command == "doctor":
        return _cmd_doctor(config, stdout=stdout)

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
