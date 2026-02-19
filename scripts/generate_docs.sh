#!/usr/bin/env bash
set -euo pipefail

# Script: Generate API documentation for FlowGate
# Description: Uses pdoc to generate HTML documentation from Python docstrings

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${PROJECT_ROOT}/docs/api/_generated"

echo "=== FlowGate API Documentation Generator ==="
echo ""
echo "Project root: ${PROJECT_ROOT}"
echo "Output directory: ${OUTPUT_DIR}"
echo ""

# Check if pdoc is available
if ! uv run python -c "import pdoc" 2>/dev/null; then
    echo "❌ pdoc is not installed"
    echo ""
    echo "Install with:"
    echo "  uv sync --group dev"
    exit 1
fi

echo "1. Cleaning old documentation..."
if [ -d "${OUTPUT_DIR}" ]; then
    rm -rf "${OUTPUT_DIR}"
    echo "   ✓ Removed old docs"
else
    echo "   ✓ No old docs to remove"
fi

echo ""
echo "2. Generating API documentation..."
cd "${PROJECT_ROOT}"
uv run pdoc --output-dir "${OUTPUT_DIR}" src/flowgate

if [ $? -eq 0 ]; then
    echo "   ✓ Documentation generated successfully"
else
    echo "   ❌ Documentation generation failed"
    exit 1
fi

echo ""
echo "3. Verifying output..."
if [ -f "${OUTPUT_DIR}/index.html" ]; then
    file_count=$(find "${OUTPUT_DIR}" -type f -name "*.html" | wc -l)
    echo "   ✓ Generated ${file_count} HTML files"
else
    echo "   ❌ Output directory not created"
    exit 1
fi

echo ""
echo "=== Documentation Generation Complete ==="
echo ""
echo "View docs at: ${OUTPUT_DIR}/index.html"
echo ""
echo "To view in browser:"
echo "  open ${OUTPUT_DIR}/index.html"
echo ""
