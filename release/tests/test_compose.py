"""Release topology boundaries independent of local developer configuration."""

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class ReleaseComposeTests(unittest.TestCase):
    def test_only_the_frontend_is_exposed_on_loopback(self):
        services = yaml.safe_load((ROOT / "release/compose.yaml").read_text())["services"]
        for name, service in services.items():
            self.assertNotIn("build", service)
            self.assertNotIn("container_name", service)
            self.assertEqual(service["restart"], "unless-stopped")
            self.assertNotIn("/var/run/docker.sock", str(service))
            if name == "frontend":
                self.assertEqual(service["ports"], ["127.0.0.1:${ALGOTRADER_UI_PORT:-8000}:8080"])
            else:
                self.assertNotIn("ports", service)
            for env_file in service.get("env_file", []):
                self.assertEqual(env_file["format"], "raw")

    def test_packaged_proxy_targets_match_managed_internal_ports(self):
        nginx = (ROOT / "release/nginx.conf").read_text()
        for host in (
            "database-accessor-api",
            "backtester-api",
            "indicator-api",
            "broker-service",
            "ingestion-service",
            "realtime-service",
        ):
            self.assertIn(f"http://{host}:8080", nginx)
        compose = yaml.safe_load((ROOT / "release/compose.yaml").read_text())
        self.assertIn(
            "REALTIME_SERVICE_HEALTH_PORT:-8081",
            str(compose["services"]["realtime-service"]["healthcheck"]),
        )

    def test_persistent_state_is_independent_of_release_files(self):
        compose = yaml.safe_load((ROOT / "release/compose.yaml").read_text())
        self.assertEqual(set(compose["volumes"]), {"timescaledb_data", "redis_data"})
        self.assertIn("-h 127.0.0.1", compose["services"]["timescaledb"]["healthcheck"]["test"][1])
        self.assertEqual(
            compose["services"]["timescaledb"]["volumes"], ["timescaledb_data:/var/lib/postgresql"]
        )
        self.assertEqual(compose["services"]["redis"]["volumes"], ["redis_data:/data"])


if __name__ == "__main__":
    unittest.main()
