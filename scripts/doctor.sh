#!/usr/bin/env sh
set -eu

CONFIG_PATH="${1:-config/routertool.yaml}"
uv run llm-router --config "$CONFIG_PATH" doctor
