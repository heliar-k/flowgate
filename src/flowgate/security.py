from __future__ import annotations

import stat
from pathlib import Path


EXPECTED_MODE = 0o600


def check_secret_file_permissions(paths: list[str | Path]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for item in paths:
        path = Path(item)
        if not path.exists():
            continue

        mode = stat.S_IMODE(path.stat().st_mode)
        if mode != EXPECTED_MODE:
            issues.append(
                {
                    "path": str(path),
                    "actual_mode": oct(mode),
                    "expected_mode": oct(EXPECTED_MODE),
                }
            )
    return issues
