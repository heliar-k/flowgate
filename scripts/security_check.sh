#!/usr/bin/env sh
set -eu

uv run python - <<'PY'
from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()

SENSITIVE_PATH_RE = re.compile(
    r"(^|/)(\.env(\..+)?|[^/]*\.(pem|key|p12|pfx|kdbx)|((auth|auths|secret|secrets)(/|$)).*)$",
    re.IGNORECASE,
)

TRACKED_ALLOWLIST_PREFIX = (
    "config/examples/",
    "docs/",
    "tests/",
)

REQUIRED_GITIGNORE_TOKENS = [
    ".env",
    ".env.*",
    "config/flowgate.yaml",
    "config/cliproxyapi.yaml",
    "config/auths/",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
]


def run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return proc.stdout


def tracked_sensitive_files() -> list[str]:
    files = [line.strip() for line in run(["git", "ls-files"]).splitlines() if line.strip()]
    findings: list[str] = []
    for rel in files:
        if rel.startswith(TRACKED_ALLOWLIST_PREFIX):
            continue
        if SENSITIVE_PATH_RE.search(rel):
            findings.append(rel)
    return findings


def permissive_secret_files() -> list[tuple[str, str]]:
    # Only inspect files that exist locally.
    candidate_globs = [
        ".router/auths/*.json",
        "auths/*.json",
        "auth/*.json",
        "config/auths/*",
    ]
    findings: list[tuple[str, str]] = []
    for pattern in candidate_globs:
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            mode = stat.S_IMODE(path.stat().st_mode)
            if mode & 0o077:
                findings.append((str(path), oct(mode)))
    return findings


def missing_gitignore_tokens() -> list[str]:
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        return REQUIRED_GITIGNORE_TOKENS

    lines = {line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()}
    return [token for token in REQUIRED_GITIGNORE_TOKENS if token not in lines]


def main() -> int:
    ok = True

    sensitive = tracked_sensitive_files()
    if sensitive:
        ok = False
        print(f"security:tracked_sensitive=fail count={len(sensitive)}")
        for rel in sensitive:
            print(f"security:tracked_sensitive:item path={rel}")
        print("security:tracked_sensitive:hint untrack secrets and move to env vars or ignored local files")
    else:
        print("security:tracked_sensitive=pass count=0")

    permissive = permissive_secret_files()
    if permissive:
        ok = False
        print(f"security:secret_permissions=fail count={len(permissive)}")
        for path, mode in permissive:
            print(f"security:secret_permissions:item path={path} mode={mode} expected=0o600")
        print("security:secret_permissions:hint run chmod 600 on secret auth files")
    else:
        print("security:secret_permissions=pass count=0")

    missing_tokens = missing_gitignore_tokens()
    if missing_tokens:
        ok = False
        print(f"security:gitignore=fail missing={','.join(missing_tokens)}")
        print("security:gitignore:hint add required sensitive-file patterns to .gitignore")
    else:
        print("security:gitignore=pass")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
PY
