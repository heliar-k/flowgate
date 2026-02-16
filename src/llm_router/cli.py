from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, TextIO

from .bootstrap import (
    DEFAULT_CLIPROXY_REPO,
    DEFAULT_CLIPROXY_VERSION,
    DEFAULT_LITELLM_VERSION,
    download_cliproxyapi_plus,
    prepare_litellm_runner,
)
from .config import ConfigError, load_router_config
from .health import check_health_url
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

    cfg["secret_files"] = [_resolve_path(base_dir, p) for p in cfg.get("secret_files", [])]

    for service in cfg.get("services", {}).values():
        command = service.get("command", {})
        cwd = command.get("cwd")
        if isinstance(cwd, str):
            command["cwd"] = _resolve_path(base_dir, cwd)

    return cfg


def _load_and_resolve_config(path: str) -> dict[str, Any]:
    cfg_path = Path(path)
    cfg = load_router_config(cfg_path)
    return _resolve_config_paths(cfg, cfg_path)


def _read_state_file(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _service_names(config: dict[str, Any], target: str) -> list[str]:
    if target == "all":
        return list(config["services"].keys())
    if target not in config["services"]:
        raise KeyError(f"Unknown service: {target}")
    return [target]


def _cmd_profile_list(config: dict[str, Any], *, stdout: TextIO) -> int:
    for name in sorted(config["profiles"].keys()):
        print(name, file=stdout)
    return 0


def _cmd_profile_set(config: dict[str, Any], profile: str, *, stdout: TextIO, stderr: TextIO) -> int:
    try:
        active_path, state_path = activate_profile(config, profile)
    except KeyError as exc:
        print(str(exc), file=stderr)
        return 2

    print(f"profile={profile}", file=stdout)
    print(f"active_config={active_path}", file=stdout)
    print(f"state_file={state_path}", file=stdout)

    # If LiteLLM is already running, apply the profile switch immediately by restart.
    supervisor = ProcessSupervisor(config["paths"]["runtime_dir"])
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

    issues = check_secret_file_permissions(config.get("secret_files", []))
    if issues:
        print(f"secret_permission_issues={len(issues)}", file=stdout)
    else:
        print("secret_permission_issues=0", file=stdout)

    return 0


def _cmd_health(config: dict[str, Any], *, stdout: TextIO) -> int:
    all_ok = True
    for name, service in sorted(config["services"].items()):
        host = service.get("host", "127.0.0.1")
        port = service.get("port")
        health_path = service.get("health_path", "/healthz")
        url = f"http://{host}:{port}{health_path}"
        ok = check_health_url(url, timeout=1.0)
        print(f"{name}:{'ok' if ok else 'fail'} url={url}", file=stdout)
        if not ok:
            all_ok = False
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
    oauth = config.get("oauth", {})
    if provider not in oauth:
        print(f"OAuth provider not configured: {provider}", file=stderr)
        return 2

    provider_cfg = oauth[provider]
    auth_url_endpoint = provider_cfg.get("auth_url_endpoint")
    status_endpoint = provider_cfg.get("status_endpoint")
    if not auth_url_endpoint or not status_endpoint:
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
        print(f"oauth_status={status}", file=stdout)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"OAuth login failed: {exc}", file=stderr)
        return 1


def _cmd_service_action(config: dict[str, Any], action: str, target: str, *, stdout: TextIO, stderr: TextIO) -> int:
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
    litellm_version: str,
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
        litellm = prepare_litellm_runner(runtime_bin_dir, version=litellm_version)
    except Exception as exc:  # noqa: BLE001
        print(f"bootstrap failed: {exc}", file=stderr)
        return 1

    print(f"cliproxyapi_plus={cliproxy}", file=stdout)
    print(f"litellm={litellm}", file=stdout)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="routerctl")
    parser.add_argument("--config", default="config/routertool.yaml")

    sub = parser.add_subparsers(dest="command", required=True)

    profile = sub.add_parser("profile")
    profile_sub = profile.add_subparsers(dest="profile_cmd", required=True)
    profile_sub.add_parser("list")
    p_set = profile_sub.add_parser("set")
    p_set.add_argument("name")

    sub.add_parser("status")
    sub.add_parser("health")

    auth = sub.add_parser("auth")
    auth_sub = auth.add_subparsers(dest="provider", required=True)
    for provider in ("codex", "copilot"):
        provider_parser = auth_sub.add_parser(provider)
        provider_sub = provider_parser.add_subparsers(dest="auth_cmd", required=True)
        login = provider_sub.add_parser("login")
        login.add_argument("--timeout", type=float, default=120)
        login.add_argument("--poll-interval", type=float, default=2)

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
    download.add_argument("--litellm-version", default=DEFAULT_LITELLM_VERSION)

    return parser


def run_cli(argv: Iterable[str], *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
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

    if args.command == "auth":
        if args.auth_cmd == "login":
            return _cmd_auth_login(
                config,
                args.provider,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
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
                litellm_version=args.litellm_version,
                stdout=stdout,
                stderr=stderr,
            )

    print("Unknown command", file=stderr)
    return 2
