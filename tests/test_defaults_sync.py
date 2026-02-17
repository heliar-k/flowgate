import re
import unittest
from pathlib import Path

from flowgate.config import load_router_config
from flowgate.constants import (
    DEFAULT_SERVICE_HOST,
    DEFAULT_SERVICE_PORTS,
    DEFAULT_SERVICE_READINESS_PATHS,
)


class DefaultsSyncTests(unittest.TestCase):
    def test_example_flowgate_services_match_constants(self):
        cfg = load_router_config(Path("config/examples/flowgate.yaml"))
        services = cfg["services"]

        for service_name, port in DEFAULT_SERVICE_PORTS.items():
            self.assertEqual(services[service_name]["port"], port)
            path = services[service_name].get("readiness_path") or services[
                service_name
            ].get("health_path")
            self.assertEqual(path, DEFAULT_SERVICE_READINESS_PATHS[service_name])

    def test_example_cliproxyapi_port_matches_constants(self):
        text = Path("config/examples/cliproxyapi.yaml").read_text(encoding="utf-8")
        host_match = re.search(r'^host:\s*"([^"]+)"\s*$', text, re.MULTILINE)
        self.assertIsNotNone(host_match)
        self.assertEqual(host_match.group(1), DEFAULT_SERVICE_HOST)

        match = re.search(r"^port:\s*(\d+)\s*$", text, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), DEFAULT_SERVICE_PORTS["cliproxyapi_plus"])

    def test_example_flowgate_urls_use_cliproxy_port(self):
        cfg = load_router_config(Path("config/examples/flowgate.yaml"))
        cliproxy_port = DEFAULT_SERVICE_PORTS["cliproxyapi_plus"]

        model_list = cfg.get("litellm_base", {}).get("model_list", [])
        default_model = next(
            model for model in model_list if model.get("model_name") == "router-default"
        )
        api_base = default_model.get("litellm_params", {}).get("api_base")
        self.assertEqual(api_base, f"http://{DEFAULT_SERVICE_HOST}:{cliproxy_port}/v1")

        oauth = cfg.get("oauth", {})
        self.assertEqual(
            oauth.get("codex", {}).get("auth_url_endpoint"),
            f"http://{DEFAULT_SERVICE_HOST}:{cliproxy_port}/v0/management/oauth/codex/auth-url",
        )
        self.assertEqual(
            oauth.get("codex", {}).get("status_endpoint"),
            f"http://{DEFAULT_SERVICE_HOST}:{cliproxy_port}/v0/management/oauth/codex/status",
        )
        self.assertEqual(
            oauth.get("copilot", {}).get("auth_url_endpoint"),
            f"http://{DEFAULT_SERVICE_HOST}:{cliproxy_port}/v0/management/oauth/github-copilot/auth-url",
        )
        self.assertEqual(
            oauth.get("copilot", {}).get("status_endpoint"),
            f"http://{DEFAULT_SERVICE_HOST}:{cliproxy_port}/v0/management/oauth/github-copilot/status",
        )


if __name__ == "__main__":
    unittest.main()
