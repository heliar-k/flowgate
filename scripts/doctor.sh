#!/usr/bin/env sh
set -eu

CONFIG_PATH="${1:-config/flowgate.yaml}"
uv run flowgate --config "$CONFIG_PATH" doctor
