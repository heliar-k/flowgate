from __future__ import annotations

import pytest

from flowgate.cliproxyapiplus import (
    build_update_info,
    is_newer_version,
    parse_version_tuple,
)


@pytest.mark.unit
def test_parse_version_tuple_extracts_numeric_parts():
    assert parse_version_tuple("v6.8.18-1") == (6, 8, 18, 1)
    assert parse_version_tuple("latest") is None


@pytest.mark.unit
def test_is_newer_version_compares_by_normalized_width():
    assert is_newer_version("v6.8.18", "v6.8.17-9") is True
    assert is_newer_version("v6.8", "v6.8.0") is False
    assert is_newer_version("v6.8.0", "v6.8") is False


@pytest.mark.unit
def test_build_update_info_returns_none_when_not_newer():
    assert (
        build_update_info(
            current_version="v6.8.18-1",
            latest_version="v6.8.18-1",
            release_url="https://example/release",
        )
        is None
    )


@pytest.mark.unit
def test_build_update_info_returns_payload_when_newer():
    assert build_update_info(
        current_version="v6.8.16-0",
        latest_version="v6.8.18-1",
        release_url=" https://example/release ",
    ) == {
        "current_version": "v6.8.16-0",
        "latest_version": "v6.8.18-1",
        "release_url": "https://example/release",
    }
