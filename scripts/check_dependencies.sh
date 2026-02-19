#!/usr/bin/env bash
# Dependency audit and update checking script
set -euo pipefail

echo "=== Dependency Audit ==="
echo ""

echo "1. Outdated dependencies:"
uv pip list --outdated || true
echo ""

echo "2. Security vulnerabilities:"
# Note: uv does not currently have a built-in audit command
# Consider using: pip-audit, safety, or GitHub Dependabot
echo "  (uv audit not available - use pip-audit or safety for vulnerability scanning)"
echo ""

echo "3. Current versions (key dependencies):"
uv pip list | grep -E "(litellm|requests|pyyaml)" || true
echo ""

echo "Audit complete."
