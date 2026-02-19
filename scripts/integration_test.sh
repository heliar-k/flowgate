#!/usr/bin/env bash
# Run FlowGate integration tests.
#
# Usage:
#   ./scripts/integration_test.sh [pytest options]
#
# Examples:
#   ./scripts/integration_test.sh
#   ./scripts/integration_test.sh -v
#   ./scripts/integration_test.sh -k test_full_lifecycle
#
# Integration tests are marked with @pytest.mark.integration and are
# skipped by default unless explicitly selected with -m integration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "FlowGate Integration Test Runner"
echo "================================="
echo "Project root : ${PROJECT_ROOT}"
echo ""

cd "${PROJECT_ROOT}"
# Run integration tests using pytest marker
uv run pytest tests/integration/ -v -m integration "$@"
