"""Lifecycle commands cannot apply an old controller to a newer installation."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release.installer.__main__ import main
from release.installer.model import (
    InstallationError,
    Locations,
    require_installed_controller,
    write_json,
)
from release.tests.test_model import manifest


class ControllerTests(unittest.TestCase):
    def test_mismatched_lifecycle_controller_stops_before_docker_or_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            locations = Locations(root / "config", root / "data", root / "state", root / "bundle")
            write_json(
                locations.record, {"project": "algotrader-123456abcdef", "version": "v2.0.0"}
            )
            write_json(locations.release_dir("v2.0.0") / "release.json", manifest("v2.0.0"))
            locations.config.mkdir()
            config = locations.config / ".env.shared"
            config.write_text("UNCHANGED=existing\n")
            for command in ("start", "stop", "status", "reconnect"):
                with (
                    self.subTest(command=command),
                    patch("sys.argv", ["installer", command]),
                    patch.dict(os.environ, {"ALGOTRADER_INSTALLER_IMAGE": "old-controller"}),
                    patch("release.installer.__main__.Locations", return_value=locations),
                    patch("release.installer.__main__.Docker") as docker,
                    patch("release.installer.__main__.Lifecycle") as lifecycle,
                ):
                    self.assertEqual(main(), 1)
                    docker.assert_not_called()
                    lifecycle.assert_not_called()
                    self.assertEqual(config.read_text(), "UNCHANGED=existing\n")

    def test_matching_installed_controller_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            locations = Locations(root / "config", root / "data", root / "state", root / "bundle")
            value = manifest("v2.0.0")
            write_json(
                locations.record, {"project": "algotrader-123456abcdef", "version": "v2.0.0"}
            )
            write_json(locations.release_dir("v2.0.0") / "release.json", value)
            require_installed_controller(locations, value["images"]["installer"])


class UpdateCommandTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.locations = Locations(root / "config", root / "data", root / "state", root / "bundle")
        self.record = {"project": "algotrader-123456abcdef", "version": "v1.0.0"}
        write_json(self.locations.record, self.record)
        self.installed = manifest("v1.0.0")
        write_json(self.locations.release_dir("v1.0.0") / "release.json", self.installed)
        self.target = manifest("v2.0.0")
        self.target["images"]["installer"] = "ghcr.io/example/installer@sha256:" + "b" * 64
        write_json(self.locations.bundle / "release.json", self.target)
        self.enterContext(
            patch("release.installer.__main__.Locations", return_value=self.locations)
        )
        self.docker = self.enterContext(patch("release.installer.__main__.Docker")).return_value
        self.enterContext(
            patch.dict(
                os.environ, {"ALGOTRADER_INSTALLER_IMAGE": self.installed["images"]["installer"]}
            )
        )
        self.latest = self.enterContext(
            patch("release.installer.__main__.latest_version", return_value="v2.0.0")
        )
        self.download = self.enterContext(patch("release.installer.__main__.download_bundle"))

    def test_current_or_ahead_stops_before_confirmation_and_download(self):
        for version in ("v0.9.0", "v1.0.0"):
            self.latest.return_value = version
            with (
                self.subTest(version=version),
                patch("sys.argv", ["installer", "update"]),
                patch("builtins.input") as prompt,
            ):
                self.assertEqual(main(), 0)
                prompt.assert_not_called()
        self.download.assert_not_called()
        self.docker.apply_upgrade.assert_not_called()

    def test_default_or_explicit_decline_or_eof_keeps_installation(self):
        for answer in ("", "n", EOFError()):
            with (
                self.subTest(answer=answer),
                patch("sys.argv", ["installer", "update"]),
                patch("builtins.input", side_effect=[answer]),
            ):
                self.assertEqual(main(), 0)
        self.download.assert_not_called()
        self.docker.apply_upgrade.assert_not_called()
        self.assertEqual(self.locations.installed(), self.record)

    def test_confirmed_update_hands_verified_bundle_and_expected_version_to_target(self):
        with (
            patch("sys.argv", ["installer", "update", "--prerelease"]),
            patch("builtins.input", return_value="yes"),
        ):
            self.assertEqual(main(), 0)
        self.latest.assert_called_once_with(True)
        version, directory = self.download.call_args.args
        self.assertEqual(version, self.target["version"])
        self.docker.apply_upgrade.assert_called_once_with(
            directory, self.download.return_value, self.record["version"]
        )
        self.assertFalse(directory.exists())
        self.assertEqual(self.locations.installed(), self.record)

    def test_verification_failure_cleans_staging_and_keeps_installed_record(self):
        self.download.side_effect = InstallationError("checksum mismatch")
        with patch("sys.argv", ["installer", "update"]), patch("builtins.input", return_value="y"):
            self.assertEqual(main(), 1)
        self.assertFalse(self.download.call_args.args[1].exists())
        self.assertEqual(self.locations.installed(), self.record)
        self.docker.apply_upgrade.assert_not_called()

    def test_intervening_upgrade_invalidates_confirmed_handoff(self):
        environment = {
            "ALGOTRADER_INSTALLER_IMAGE": self.target["images"]["installer"],
            "ALGOTRADER_UPGRADE_FROM": "v0.9.0",
        }
        with (
            patch("sys.argv", ["installer", "upgrade"]),
            patch.dict(os.environ, environment),
            patch("release.installer.lifecycle.Lifecycle.upgrade") as apply,
        ):
            self.assertEqual(main(), 1)
        apply.assert_not_called()
        self.assertEqual(self.locations.installed(), self.record)
