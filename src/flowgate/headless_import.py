from __future__ import annotations

import json
from pathlib import Path

from .observability import measure_time


OUTPUT_FILENAME = "codex-headless-import.json"


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError("Headless auth file must be a JSON object")
    return data


@measure_time("oauth_import_headless")
def import_codex_headless_auth(source: str | Path, dest_dir: str | Path) -> Path:
    src = Path(source).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source auth file not found: {src}")

    data = _load_json(src)
    tokens = data.get("tokens")
    if not isinstance(tokens, dict):
        raise ValueError("Headless auth file missing tokens object")

    access_token = str(tokens.get("access_token", "")).strip()
    refresh_token = str(tokens.get("refresh_token", "")).strip()
    id_token = str(tokens.get("id_token", "")).strip()
    account_id = str(tokens.get("account_id", "")).strip()

    if not access_token:
        raise ValueError("Headless auth file missing tokens.access_token")
    if not refresh_token:
        raise ValueError("Headless auth file missing tokens.refresh_token")

    payload = {
        "type": "codex",
        "token_type": "bearer",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "id_token": id_token,
        "account_id": account_id,
    }

    dst_dir = Path(dest_dir).expanduser().resolve()
    dst_dir.mkdir(parents=True, exist_ok=True)
    out = dst_dir / OUTPUT_FILENAME
    out.write_text(json.dumps(payload), encoding="utf-8")
    out.chmod(0o600)
    return out
