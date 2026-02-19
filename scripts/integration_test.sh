#!/usr/bin/env bash
# Run FlowGate integration tests.
#
# Usage:
#   ./scripts/integration_test.sh [unittest discover options]
#
# Examples:
#   ./scripts/integration_test.sh
#   ./scripts/integration_test.sh -v
#   ./scripts/integration_test.sh -k test_full_lifecycle
#
# The integration tests require a real process environment and are skipped
# by default in CI.  This script sets RUN_INTEGRATION_TESTS=1 before
# running them so they are not skipped.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "FlowGate Integration Test Runner"
echo "================================="
echo "Project root : ${PROJECT_ROOT}"
echo ""

export RUN_INTEGRATION_TESTS=1

cd "${PROJECT_ROOT}"
# Run all tests (including integration tests) with RUN_INTEGRATION_TESTS=1.
# Filter output to show only integration test names and the final summary.
uv run python -m unittest discover -s tests -p "test_*.py" -v "$@" | grep -E "(^(test_|setUpClass).*integration\.|^(Ran|OK|FAILED))"
