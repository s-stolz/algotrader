"""The installer uses canonical configuration inputs without exposing secrets."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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
            self.assertEqual(choose_port(Mock(), release), 8088)
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
