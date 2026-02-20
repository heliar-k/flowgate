#!/usr/bin/env bash
# Check markdown documentation for broken internal links

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Checking documentation links in: $PROJECT_ROOT"
echo ""

TOTAL_LINKS=0
BROKEN_LINKS=0
VALID_LINKS=0

# Find all markdown files
cd "$PROJECT_ROOT"
MARKDOWN_FILES=$(find . -name "*.md" \
    -not -path "./node_modules/*" \
    -not -path "./.venv/*" \
    -not -path "./.uv-cache/*" \
    -not -path "./.worktrees/*" \
    -not -path "./.router/*" \
    -type f)

FILE_COUNT=$(echo "$MARKDOWN_FILES" | wc -l | xargs)
echo "Found $FILE_COUNT markdown files"
echo ""

# Extract and check links
for file in $MARKDOWN_FILES; do
    # Extract markdown links [text](path) - only local paths
    # Skip http/https URLs and anchors
    grep -oE '\]\([^)]+\)' "$file" 2>/dev/null | \
    sed 's/](\(.*\))/\1/' | \
    grep -v '^http' | \
    grep -v '^#' | \
    while read -r link; do
        TOTAL_LINKS=$((TOTAL_LINKS + 1))

        # Remove anchor
        link_file="${link%%#*}"

        # Skip if empty
        [[ -z "$link_file" ]] && continue

        # Get directory of current file
        file_dir=$(dirname "$file")

        # Resolve path
        if [[ "$link_file" = /* ]]; then
            # Absolute path from root
            target=".$link_file"
        else
            # Relative path
            target="$file_dir/$link_file"
        fi

        # Check if target exists
        if [[ -e "$target" ]]; then
            VALID_LINKS=$((VALID_LINKS + 1))
        else
            BROKEN_LINKS=$((BROKEN_LINKS + 1))
            echo -e "${RED}✗ Broken link${NC}"
            echo "  File: $file"
            echo "  Link: $link"
            echo "  Expected: $target"
            echo ""
        fi
    done
done

# Summary
echo "========================================"
echo "Summary"
echo "========================================"
echo "Total links checked: $TOTAL_LINKS"
echo -e "${GREEN}Valid links: $VALID_LINKS${NC}"
echo -e "${RED}Broken links: $BROKEN_LINKS${NC}"
echo ""

if [[ $BROKEN_LINKS -gt 0 ]]; then
    echo -e "${RED}❌ Found broken links!${NC}"
    exit 1
else
    echo -e "${GREEN}✅ All links are valid!${NC}"
    exit 0
fi
