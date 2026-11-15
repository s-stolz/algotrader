"""The installer uses canonical configuration inputs without exposing secrets."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from release.installer.configuration import authorize, choose_port, render_configuration
from release.installer.model import Locations, Release
from release.tests.test_model import manifest
from scripts import generate_env


class ConfigurationTests(unittest.TestCase):
    def test_generation_preserves_secret_values_and_expiry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            locations = Locations(root / "config", root / "data", root / "state", root / "bundle")
            locations.config.mkdir()
            release_dir = locations.release_dir("v1.0.0")
            release_dir.mkdir(parents=True)
            (release_dir / "topology.yaml").write_bytes(generate_env.TOPOLOGY_PATH.read_bytes())
            secrets = {key: "value" for key in generate_env.REQUIRED_SECRETS}
            secrets.update(
                ACCOUNT_ID="123",
                CTRADER_HOST_TYPE="demo",
                CTRADER_ACCESS_TOKEN_EXPIRES_AT="2000000000",
                CTRADER_SECRET="literal$secret",
            )
            (locations.config / ".env.secrets.local").write_text(generate_env.format_env(secrets))
            render_configuration(locations, {"version": "v1.0.0"})
            broker = generate_env.read_env(locations.config / ".env.secrets.broker")
            self.assertEqual(broker["CTRADER_SECRET"], "literal$secret")
            self.assertEqual(broker["CTRADER_ACCESS_TOKEN_EXPIRES_AT"], "2000000000")
            shared = (locations.config / ".env.shared").read_text()
            self.assertNotIn("literal$secret", shared)
            self.assertIn("MODE=production", shared)
            with self.assertRaisesRegex(Exception, "cannot change"):
                render_configuration(
                    locations,
                    {
                        "version": "v1.0.0",
                        "account_id": "another-account",
                        "environment": "demo",
                    },
                )

    def test_available_default_port_does_not_prompt(self):
        value = manifest()
        release = Release(value["version"], value["images"], 18)
        with patch("release.installer.configuration.ask") as ask:
            self.assertEqual(choose_port(Mock(), release), 8000)
        ask.assert_not_called()

    def test_reconnect_preserves_previous_config_when_authorization_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            locations = Locations(root, root, root, root)
            original = (
                "ACCOUNT_ID=12\nCTRADER_HOST_TYPE=demo\n"
                "CTRADER_CLIENT_ID=id\nCTRADER_SECRET=secret\n"
            )
            (root / ".env.secrets.local").write_text(original)
            (root / ".env.shared").write_text(
                "BROKER_REDIS_URL=redis://redis:6379/0\n"
                "BROKER_TOKEN_REDIS_KEY=broker:auth:ctrader:current\n"
            )
            docker = Mock()
            docker.host_path.return_value = "/host/config"
            docker.run.side_effect = RuntimeError("authorization rejected")
            value = manifest()
            release = Release(value["version"], value["images"], 18)
            with (
                patch("release.installer.configuration.ask", side_effect=["id", "secret"]),
                patch("release.installer.configuration.choose", return_value="accounts"),
            ):
                with self.assertRaises(RuntimeError):
                    authorize(
                        locations,
                        docker,
                        release,
                        {"project": "algotrader-a", "account_id": "12", "environment": "demo"},
                    )
            self.assertEqual((root / ".env.secrets.local").read_text(), original)
            arguments = docker.run.call_args.args[0]
            self.assertIn("127.0.0.1:8080:8080", arguments)
            self.assertEqual(arguments[arguments.index("--bind-address") + 1], "0.0.0.0")

    def test_reconnect_rejects_hand_edited_account_binding_before_authentication(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            locations = Locations(root, root, root, root)
            (root / ".env.secrets.local").write_text("ACCOUNT_ID=other\nCTRADER_HOST_TYPE=demo\n")
            value = manifest()
            docker = Mock()
            with self.assertRaisesRegex(Exception, "cannot change"):
                authorize(
                    locations,
                    docker,
                    Release(value["version"], value["images"], 18),
                    {"account_id": "original", "environment": "demo"},
                )
            docker.run.assert_not_called()


class LegacyReleaseConfigurationTests(unittest.TestCase):
    def test_legacy_network_overrides_do_not_change_new_packaged_endpoints(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            locations = Locations(root / "config", root / "data", root / "state", root / "bundle")
            locations.config.mkdir()
            release_dir = locations.release_dir("v0.0.2")
            release_dir.mkdir(parents=True)
            (release_dir / "topology.yaml").write_bytes(generate_env.TOPOLOGY_PATH.read_bytes())
            override = {
                "services": {
                    "database_accessor_api": {
                        "network": {"port": 8000},
                        "resources": {"cpus": 1.75},
                        "logging": {"level": "DEBUG"},
                    },
                    "indicator_api": {"network": {"port": 8010, "published_port": 8000}},
                    "backtester": {"api": {"network": {"port": 8020}}},
                    "broker_service": {"network": {"port": 8050}},
                    "ingestion_service": {"network": {"port": 8000}},
                    "realtime_service": {
                        "network": {
                            "websocket": {"port": 8765},
                            "health": {"port": 8080, "published_port": 8080},
                        }
                    },
                }
            }
            original = yaml.safe_dump(override)
            (locations.config / "topology.local.yaml").write_text(original)
            secrets = {key: "value" for key in generate_env.REQUIRED_SECRETS}
            secrets.update(ACCOUNT_ID="123", CTRADER_HOST_TYPE="demo")
            (locations.config / ".env.secrets.local").write_text(generate_env.format_env(secrets))
            record = {"version": "v0.0.2", "ui_port": 8088, "project": "algotrader-123456abcdef"}
            saved = copy.deepcopy(record)
            render_configuration(locations, record)
            shared = generate_env.read_env(locations.config / ".env.shared")
            for key in (
                "DATABASE_ACCESSOR_PORT",
                "INDICATOR_API_PORT",
                "BACKTESTER_API_PORT",
                "BROKER_SERVICE_PORT",
                "INGESTION_API_PORT",
                "REALTIME_SERVICE_WS_PORT",
                "FRONTEND_PORT",
            ):
                self.assertEqual(shared[key], "8080", key)
            self.assertEqual(shared["REALTIME_SERVICE_HEALTH_PORT"], "8081")
            self.assertEqual(shared["COMPOSE_DATABASE_ACCESSOR_API_CPUS"], "1.75")
            self.assertEqual(shared["DATABASE_ACCESSOR_LOG_LEVEL"], "DEBUG")
            self.assertEqual((locations.config / "topology.local.yaml").read_text(), original)
            self.assertEqual(record, saved)
