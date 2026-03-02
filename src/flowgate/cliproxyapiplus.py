"""Backward-compat shim — moved to flowgate.core.cliproxyapiplus."""
from .core.cliproxyapiplus import *  # noqa: F401, F403
from .core.cliproxyapiplus import parse_version_tuple, is_newer_version, build_update_info, build_latest_release_url, parse_latest_release_payload, fetch_latest_release, read_installed_version, write_installed_version, check_update, check_latest_version, perform_update  # explicit
