from __future__ import annotations

from pathlib import Path
from typing import Callable

from .headless_import import import_codex_headless_auth


HeadlessImportHandler = Callable[[str, str], Path]


def headless_import_handlers() -> dict[str, HeadlessImportHandler]:
    return {
        "codex": import_codex_headless_auth,
    }


def get_headless_import_handler(provider: str) -> HeadlessImportHandler | None:
    return headless_import_handlers().get(provider)
