from __future__ import annotations

from flowgate.cliproxyapiplus import (
    build_latest_release_url,
    parse_latest_release_payload,
)


def test_build_latest_release_url_uses_repo_name():
    assert (
        build_latest_release_url("router-for-me/CLIProxyAPIPlus")
        == "https://api.github.com/repos/router-for-me/CLIProxyAPIPlus/releases/latest"
    )


def test_parse_latest_release_payload_normalizes_strings():
    latest, release_url = parse_latest_release_payload(
        {
            "tag_name": " v6.8.18-1 ",
            "html_url": " https://github.com/example/release ",
        }
    )
    assert latest == "v6.8.18-1"
    assert release_url == "https://github.com/example/release"


def test_parse_latest_release_payload_missing_fields_returns_empty_strings():
    latest, release_url = parse_latest_release_payload({})
    assert latest == ""
    assert release_url == ""
