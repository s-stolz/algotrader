"""Lifecycle commands cannot apply an old controller to a newer installation."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release.installer.__main__ import main
from release.installer.model import Locations, require_installed_controller, write_json
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
