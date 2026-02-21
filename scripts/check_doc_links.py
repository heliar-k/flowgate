#!/usr/bin/env python3
"""Check markdown documentation for broken internal links.

Usage:
  ./scripts/check_doc_links.py
  uv run python scripts/check_doc_links.py

Checks all .md files in the project for broken internal links
(skips external http/https URLs). Exits with code 1 if broken
links are found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# ANSI colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"

HELP_TEXT = """\
check_doc_links - Markdown 文档链接检查工具

用法:
  ./scripts/check_doc_links.py

说明:
  扫描项目中所有 .md 文件，检查内部链接是否指向存在的文件。
  跳过外部链接 (http/https/mailto) 和纯锚点链接 (#)。

退出码:
  0   所有内部链接有效
  1   存在断链

示例:
  ./scripts/check_doc_links.py                  检查所有文档链接
  uv run python scripts/check_doc_links.py      通过 uv 运行"""

EXCLUDE_DIRS = {".venv", ".uv-cache", ".router", ".git", "node_modules", ".worktrees"}


def find_markdown_files(root: Path) -> list[Path]:
    """Find all markdown files, excluding certain directories."""
    markdown_files = []
    for md_file in root.rglob("*.md"):
        skip = False
        for part in md_file.relative_to(root).parts:
            if part in EXCLUDE_DIRS:
                skip = True
                break
        if not skip:
            markdown_files.append(md_file)

    return markdown_files


def extract_links(content: str) -> list[str]:
    """Extract markdown links from content."""
    pattern = r"\[([^\]]*)\]\(([^\)]+)\)"
    matches = re.findall(pattern, content)
    return [url for _, url in matches]


def is_external_link(link: str) -> bool:
    """Check if link is external (http/https/mailto)."""
    return link.startswith(("http://", "https://", "mailto:"))


def resolve_link(md_file: Path, link: str, root: Path) -> Path | None:
    """Resolve a link relative to the markdown file."""
    link_without_anchor = link.split("#")[0]

    if not link_without_anchor:
        return None

    if link_without_anchor.startswith("/"):
        return root / link_without_anchor.lstrip("/")

    return (md_file.parent / link_without_anchor).resolve()


def main() -> int:
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(HELP_TEXT)
        return 0

    script_path = Path(__file__).resolve()
    root = script_path.parent.parent

    print(f"Checking documentation links in: {root}")
    print()

    markdown_files = find_markdown_files(root)
    print(f"Found {len(markdown_files)} markdown files")
    print()

    total_links = 0
    broken_links = 0
    valid_links = 0
    external_links = 0
    broken_link_details = []

    for md_file in sorted(markdown_files):
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"{YELLOW}Warning: Could not read {md_file}: {e}{NC}")
            continue

        links = extract_links(content)

        for link in links:
            total_links += 1

            if is_external_link(link):
                external_links += 1
                continue

            if link.startswith("#"):
                continue

            target = resolve_link(md_file, link, root)

            if target is None:
                continue

            if target.exists():
                valid_links += 1
            else:
                broken_links += 1
                broken_link_details.append(
                    {"file": md_file.relative_to(root), "link": link, "target": target}
                )

    if broken_link_details:
        print(f"{RED}Broken Links Found:{NC}")
        print()
        for detail in broken_link_details:
            print(f"{RED}Broken link{NC}")
            print(f"  File: {detail['file']}")
            print(f"  Link: {detail['link']}")
            print(f"  Expected: {detail['target']}")
            print()

    print("=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"Total links checked:   {total_links}")
    print(f"{GREEN}Valid links:{NC}           {valid_links}")
    print(f"{YELLOW}External links:{NC}        {external_links} (skipped)")
    print(f"{RED}Broken links:{NC}          {broken_links}")
    print()

    if broken_links > 0:
        print(f"{RED}Found {broken_links} broken link(s)!{NC}")
        return 1
    else:
        print(f"{GREEN}All internal links are valid!{NC}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
