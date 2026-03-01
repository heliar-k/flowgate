from __future__ import annotations

import re


def parse_version_tuple(version: str) -> tuple[int, ...] | None:
    """Convert a version string into a tuple of ints, or None if no digits."""
    parts = re.findall(r"\d+", version)
    if not parts:
        return None
    return tuple(int(part) for part in parts)


def is_newer_version(latest: str, current: str) -> bool:
    """Return True when latest is newer than current."""
    latest_tuple = parse_version_tuple(latest)
    current_tuple = parse_version_tuple(current)
    if latest_tuple is None or current_tuple is None:
        return latest.strip() != current.strip()

    width = max(len(latest_tuple), len(current_tuple))
    latest_tuple = latest_tuple + (0,) * (width - len(latest_tuple))
    current_tuple = current_tuple + (0,) * (width - len(current_tuple))
    return latest_tuple > current_tuple


def build_update_info(
    *, current_version: str, latest_version: str, release_url: str
) -> dict[str, str] | None:
    """Create update info payload when latest_version is newer than current_version."""
    current = str(current_version).strip()
    latest = str(latest_version).strip()
    release = str(release_url).strip()
    if not latest:
        return None
    if not is_newer_version(latest, current):
        return None
    return {
        "current_version": current,
        "latest_version": latest,
        "release_url": release,
    }
