from __future__ import annotations

import io
import json
import os
import platform
import tarfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_CLIPROXY_REPO = "router-for-me/CLIProxyAPIPlus"
DEFAULT_CLIPROXY_VERSION = "v6.8.16-0"
DEFAULT_LITELLM_VERSION = "1.75.8"


def detect_platform() -> tuple[str, str]:
    os_raw = platform.system().lower()
    arch_raw = platform.machine().lower()

    if os_raw.startswith("darwin"):
        os_name = "darwin"
    elif os_raw.startswith("linux"):
        os_name = "linux"
    else:
        raise RuntimeError(f"Unsupported OS: {os_raw}")

    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    arch = arch_map.get(arch_raw)
    if arch is None:
        raise RuntimeError(f"Unsupported architecture: {arch_raw}")

    return os_name, arch


def pick_release_asset(assets: list[dict], *, os_name: str, arch: str) -> dict:
    candidates = []
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if "cliproxyapi" not in name:
            continue
        score = 0
        if os_name in name:
            score += 4
        if arch in name:
            score += 4
        if name.endswith(".tar.gz"):
            score += 2
        if name.endswith(".zip"):
            score += 1
        candidates.append((score, asset))

    if not candidates:
        raise RuntimeError("No CLIProxyAPIPlus release asset matched current platform")

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best = candidates[0]
    if best_score < 4:
        raise RuntimeError(
            "Release assets found but none look compatible with current platform"
        )
    return best


def _http_get_json(url: str) -> dict:
    req = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "flowgate-bootstrap",
        },
    )
    with urlopen(req, timeout=30) as resp:  # nosec B310
        payload = resp.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError("Invalid JSON response from release API")
    return data


def _http_get_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "flowgate-bootstrap"})
    with urlopen(req, timeout=120) as resp:  # nosec B310
        return resp.read()


def _extract_binary_from_bytes(data: bytes, asset_name: str) -> bytes:
    lower = asset_name.lower()
    preferred_basenames = {
        "cliproxyapiplus",
        "cliproxyapi",
        "cliproxyapiplus.exe",
        "cliproxyapi.exe",
        "cli-proxy-api-plus",
        "cli-proxy-api-plus.exe",
    }

    if lower.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            for member in members:
                base = Path(member.name).name.lower()
                if base in preferred_basenames:
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        continue
                    return extracted.read()
            for member in members:
                if member.mode & 0o111:
                    extracted = tf.extractfile(member)
                    if extracted is not None:
                        return extracted.read()
            if members:
                extracted = tf.extractfile(members[0])
                if extracted is not None:
                    return extracted.read()

    if lower.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            for name in names:
                base = Path(name).name.lower()
                if base in preferred_basenames:
                    return zf.read(name)
            for name in names:
                base = Path(name).name.lower()
                if "cli-proxy-api-plus" in base or "cliproxyapi" in base:
                    return zf.read(name)
            if names:
                return zf.read(names[0])

    return data


def download_cliproxyapi_plus(
    bin_dir: str | Path,
    *,
    version: str = DEFAULT_CLIPROXY_VERSION,
    repo: str = DEFAULT_CLIPROXY_REPO,
) -> Path:
    bin_path = Path(bin_dir)
    bin_path.mkdir(parents=True, exist_ok=True)

    os_name, arch = detect_platform()
    if version == "latest":
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    else:
        api_url = f"https://api.github.com/repos/{repo}/releases/tags/{version}"

    release = _http_get_json(api_url)
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise RuntimeError("Release payload missing assets list")

    chosen = pick_release_asset(assets, os_name=os_name, arch=arch)
    download_url = chosen.get("browser_download_url")
    if not isinstance(download_url, str) or not download_url:
        raise RuntimeError("Chosen asset has no browser_download_url")

    blob = _http_get_bytes(download_url)
    binary = _extract_binary_from_bytes(blob, str(chosen.get("name", "")))

    target = bin_path / "CLIProxyAPIPlus"
    target.write_bytes(binary)
    target.chmod(0o755)
    return target


def prepare_litellm_runner(
    bin_dir: str | Path, *, version: str = DEFAULT_LITELLM_VERSION
) -> Path:
    bin_path = Path(bin_dir)
    bin_path.mkdir(parents=True, exist_ok=True)

    runner = bin_path / "litellm"
    script = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'project_root="$(cd "$(dirname "$0")/../../.." && pwd)"\n'
        'exec uv run --project "$project_root" --group runtime litellm "$@"\n'
    )
    runner.write_text(script, encoding="utf-8")
    runner.chmod(0o755)
    return runner


def validate_cliproxy_binary(path: str | Path) -> bool:
    target = Path(path)
    if not target.exists() or not target.is_file():
        return False
    if target.stat().st_size < 1_000_000:
        return False
    if not os.access(target, os.X_OK):
        return False
    return True


def validate_litellm_runner(
    path: str | Path, *, version: str = DEFAULT_LITELLM_VERSION
) -> bool:
    target = Path(path)
    if not target.exists() or not target.is_file():
        return False
    if not os.access(target, os.X_OK):
        return False

    content = target.read_text(encoding="utf-8")
    if "uv run --project" not in content:
        return False
    if "--group runtime litellm" not in content:
        return False
    if 'litellm "$@"' not in content:
        return False
    return True
