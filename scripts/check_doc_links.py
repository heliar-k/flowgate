#!/usr/bin/env python3
"""Check markdown documentation for broken internal links."""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# ANSI colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'


def find_markdown_files(root: Path) -> List[Path]:
    """Find all markdown files, excluding certain directories."""
    exclude_dirs = {'.venv', '.uv-cache', '.router', '.git', 'node_modules'}

    markdown_files = []
    for md_file in root.rglob('*.md'):
        # Check if any directory component matches exclude list
        # Skip hidden files at root (like .github)
        skip = False
        for part in md_file.relative_to(root).parts:
            if part in exclude_dirs:
                skip = True
                break
        if not skip:
            markdown_files.append(md_file)

    return markdown_files


def extract_links(content: str) -> List[str]:
    """Extract markdown links from content."""
    # Pattern: [text](url)
    pattern = r'\[([^\]]*)\]\(([^\)]+)\)'
    matches = re.findall(pattern, content)
    return [url for _, url in matches]


def is_external_link(link: str) -> bool:
    """Check if link is external (http/https/mailto)."""
    return link.startswith(('http://', 'https://', 'mailto:'))


def resolve_link(md_file: Path, link: str, root: Path) -> Path:
    """Resolve a link relative to the markdown file."""
    # Remove anchor
    link_without_anchor = link.split('#')[0]

    if not link_without_anchor:
        return None

    # Absolute path from root
    if link_without_anchor.startswith('/'):
        return root / link_without_anchor.lstrip('/')

    # Relative path
    return (md_file.parent / link_without_anchor).resolve()


def main():
    """Main function."""
    # Get script directory and project root
    script_path = Path(__file__).resolve()
    root = script_path.parent.parent

    print(f"Checking documentation links in: {root}")
    print()

    # Find all markdown files
    markdown_files = find_markdown_files(root)
    print(f"Found {len(markdown_files)} markdown files")
    print()

    total_links = 0
    broken_links = 0
    valid_links = 0
    external_links = 0
    broken_link_details = []

    # Check each file
    for md_file in sorted(markdown_files):
        try:
            content = md_file.read_text(encoding='utf-8')
        except Exception as e:
            print(f"{YELLOW}⚠ Warning: Could not read {md_file}: {e}{NC}")
            continue

        links = extract_links(content)

        for link in links:
            total_links += 1

            # Skip external links
            if is_external_link(link):
                external_links += 1
                continue

            # Skip anchor-only links
            if link.startswith('#'):
                continue

            # Resolve and check link
            target = resolve_link(md_file, link, root)

            if target is None:
                # Anchor-only link after removing anchor
                continue

            if target.exists():
                valid_links += 1
            else:
                broken_links += 1
                broken_link_details.append({
                    'file': md_file.relative_to(root),
                    'link': link,
                    'target': target
                })

    # Print broken links
    if broken_link_details:
        print(f"{RED}Broken Links Found:{NC}")
        print()
        for detail in broken_link_details:
            print(f"{RED}✗ Broken link{NC}")
            print(f"  File: {detail['file']}")
            print(f"  Link: {detail['link']}")
            print(f"  Expected: {detail['target']}")
            print()

    # Print summary
    print("=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"Total links checked:   {total_links}")
    print(f"{GREEN}Valid links:{NC}           {valid_links}")
    print(f"{YELLOW}External links:{NC}        {external_links} (skipped)")
    print(f"{RED}Broken links:{NC}          {broken_links}")
    print()

    if broken_links > 0:
        print(f"{RED}❌ Found {broken_links} broken link(s)!{NC}")
        return 1
    else:
        print(f"{GREEN}✅ All internal links are valid!{NC}")
        return 0


if __name__ == '__main__':
    sys.exit(main())
