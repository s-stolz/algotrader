"""Upgrade admission, backup ordering and failure containment."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from release.installer.lifecycle import APPLICATION_SERVICES, Lifecycle
from release.installer.model import InstallationError, Locations, Release, write_json
from release.tests.test_model import manifest


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.locations = Locations(root / "config", root / "data", root / "state", root / "bundle")
        self.record = {
            "schema_version": 1,
            "project": "algotrader-123456abcdef",
            "version": "v1.0.0",
            "ui_port": 8088,
            "stopped": False,
        }
        write_json(self.locations.record, self.record)
        write_json(self.locations.release_dir("v1.0.0") / "release.json", manifest())
        self.docker = Mock()
        self.docker.sql.return_value = "f"
        self.lifecycle = Lifecycle(self.locations, self.docker)
        target = manifest("v1.1.0-alpha.1")
        self.target = Release(target["version"], target["images"], 18)
        self.prepare = patch("release.installer.lifecycle.prepare_release").start()
        self.render = patch("release.installer.lifecycle.render_configuration").start()
        self.addCleanup(patch.stopall)

    def test_busy_backtests_do_not_stop_worker_or_take_backup(self):
        self.docker.sql.return_value = "t"
        with patch.object(self.lifecycle, "backup") as backup:
            with self.assertRaisesRegex(InstallationError, "queued/running"):
                self.lifecycle.upgrade(self.target)
        backup.assert_not_called()
        self.render.assert_not_called()
        commands = [call.args[1] for call in self.docker.compose.call_args_list]
        self.assertIn(["stop", "--timeout", "60", "frontend", "backtester-api"], commands)
        self.assertFalse(
            any("backtester-worker" in args and args[0] == "stop" for args in commands)
        )
        self.assertNotIn("pending_upgrade", self.locations.installed())

    def test_backup_failure_does_not_apply_new_config_or_migrations(self):
        with patch.object(self.lifecycle, "backup", side_effect=InstallationError("disk full")):
            with self.assertRaisesRegex(InstallationError, "disk full"):
                self.lifecycle.upgrade(self.target)
        self.render.assert_not_called()
        self.assertNotIn("pending_upgrade", self.locations.installed())
        commands = [call.args[1] for call in self.docker.compose.call_args_list]
        self.assertFalse(any("--in-container" in args for args in commands))
        self.assertEqual(commands[-1][0], "up")

    def test_migration_failure_leaves_writers_stopped_and_recovery_marker(self):
        def compose(record, args, **kwargs):
            if "--in-container" in args:
                raise InstallationError("migration rejected")
            return ""

        self.docker.compose.side_effect = compose
        with patch.object(
            self.lifecycle, "backup", return_value=self.locations.state / "backups/one"
        ):
            with self.assertRaisesRegex(InstallationError, "migration rejected"):
                self.lifecycle.upgrade(self.target)
        saved = self.locations.installed()
        self.assertEqual(saved["version"], "v1.0.0")
        self.assertEqual(saved["pending_upgrade"]["version"], self.target.version)
        with self.assertRaisesRegex(InstallationError, "RECOVERY"):
            self.lifecycle.start()
        commands = [call.args[1] for call in self.docker.compose.call_args_list]
        self.assertIn(["stop", "--timeout", "60", *APPLICATION_SERVICES, "redis"], commands)
        self.assertFalse(any(args[0] == "up" and "--wait-timeout" in args for args in commands))

    def test_success_changes_version_only_after_migration_and_readiness(self):
        observed = []

        def ready(record):
            observed.append(self.locations.installed()["version"])

        with (
            patch.object(
                self.lifecycle, "backup", return_value=self.locations.state / "backups/one"
            ),
            patch.object(self.lifecycle, "check_ready", side_effect=ready),
        ):
            self.lifecycle.upgrade(self.target)
        self.assertEqual(observed, ["v1.0.0"])
        self.assertEqual(self.locations.installed()["version"], self.target.version)
        self.assertNotIn("pending_upgrade", self.locations.installed())

    def test_downgrade_is_rejected_before_docker_mutation(self):
        old = manifest("v0.9.0")
        with self.assertRaisesRegex(InstallationError, "newer"):
            self.lifecycle.upgrade(Release(old["version"], old["images"], 18))
        self.docker.pull.assert_not_called()
        self.docker.compose.assert_not_called()

    def test_failed_reconnect_never_restarts_broker_or_promotes_configuration(self):
        with patch(
            "release.installer.lifecycle.authorize",
            side_effect=InstallationError("Redis unavailable"),
        ):
            with self.assertRaisesRegex(InstallationError, "Redis unavailable"):
                self.lifecycle.reconnect()
        self.render.assert_not_called()
        self.assertTrue(self.locations.installed()["pending_reconnect"])
        commands = [call.args[1] for call in self.docker.compose.call_args_list]
        self.assertFalse(any(args[0] == "up" and "broker-service" in args for args in commands))
        with self.assertRaisesRegex(InstallationError, "reconnect again"):
            self.lifecycle.start()
