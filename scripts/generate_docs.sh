#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

show_help() {
    cat <<'HELP'
generate_docs - FlowGate API 文档生成脚本

用法:
  ./scripts/generate_docs.sh

说明:
  使用 pdoc 从 Python docstring 生成 HTML API 文档。
  输出目录: docs/api/_generated/

前置条件:
  需要安装 pdoc (通过 uv sync --group dev)

示例:
  ./scripts/generate_docs.sh                    生成文档
  ./scripts/generate_docs.sh && open docs/api/_generated/index.html
HELP
}

. "$SCRIPT_DIR/_common.sh"
check_help "$@"

PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="${PROJECT_ROOT}/docs/api/_generated"

echo "=== FlowGate API Documentation Generator ==="
echo ""
echo "Project root: ${PROJECT_ROOT}"
echo "Output directory: ${OUTPUT_DIR}"
echo ""

# Check if pdoc is available
if ! uv run python -c "import pdoc" 2>/dev/null; then
    echo "pdoc is not installed" >&2
    echo "" >&2
    echo "Install with:" >&2
    echo "  uv sync --group dev" >&2
    exit 1
fi

echo "1. Cleaning old documentation..."
if [ -d "${OUTPUT_DIR}" ]; then
    rm -rf "${OUTPUT_DIR}"
    echo "   Removed old docs"
else
    echo "   No old docs to remove"
fi

echo ""
echo "2. Generating API documentation..."
cd "${PROJECT_ROOT}"
uv run pdoc --output-dir "${OUTPUT_DIR}" src/flowgate

if [ $? -eq 0 ]; then
    echo "   Documentation generated successfully"
else
    echo "   Documentation generation failed" >&2
    exit 1
fi

echo ""
echo "3. Verifying output..."
if [ -f "${OUTPUT_DIR}/index.html" ]; then
    file_count=$(find "${OUTPUT_DIR}" -type f -name "*.html" | wc -l)
    echo "   Generated ${file_count} HTML files"
else
    echo "   Output directory not created" >&2
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
