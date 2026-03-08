"""Guard tests to keep Python imports absolute."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = (
    ROOT / "src" / "flowgate",
    ROOT / "tests" / "integration",
    ROOT / "tests" / "fixtures",
)


def _relative_import_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for directory in SCAN_DIRS:
        for path in sorted(directory.rglob("*.py")):
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(module):
                if not isinstance(node, ast.ImportFrom) or node.level <= 0:
                    continue

                module_name = node.module or ""
                import_path = f"{'.' * node.level}{module_name}"
                relative_path = path.relative_to(root)
                violations.append(
                    f"{relative_path}:{node.lineno}: relative import {import_path!r}"
                )
    return violations


def test_python_packages_use_absolute_imports() -> None:
    violations = _relative_import_violations(ROOT)

    assert not violations, "Found relative imports:\n" + "\n".join(violations)
