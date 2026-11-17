"""Docker Desktop path translation and command argument integrity."""

import csv
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from release.installer.docker import Docker, bind_mount
from release.installer.model import InstallationError, Locations, Release
from release.tests.test_model import manifest


class DockerTests(unittest.TestCase):
    def test_windows_and_macos_paths_use_daemon_reported_mounts(self):
        for source in (
            "/run/desktop/mnt/host/c/Users/A User/AppData/Local/AlgoTrader/config",
            "/host_mnt/Users/a/Library/Application Support/AlgoTrader/config",
        ):
            docker = Docker(Locations())
            docker.controller = "test-controller"
            mounts = [
                {
                    "Type": "bind",
                    "Destination": dest,
                    "Source": source if dest == "/config" else "/host" + dest,
                }
                for dest in ("/config", "/data", "/state")
            ]
            with patch.object(docker, "run", return_value=json.dumps([{"Mounts": mounts}])):
                docker.discover_mounts()
            self.assertEqual(docker.host_path(Path("/config/broker.env")), source + "/broker.env")
            with self.assertRaises(InstallationError):
                docker.host_path(Path("/unmounted/secrets"))

    def test_mount_arguments_preserve_spaces_commas_and_quotes(self):
        source = '/host/Name with spaces, and "quotes"/config'
        argument = bind_mount(source, "/config")
        fields = next(csv.reader(io.StringIO(argument)))
        self.assertEqual(fields, ["type=bind", "source=" + source, "target=/config"])

    def test_commands_do_not_use_a_shell(self):
        docker = Docker(Locations())
        with patch("subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = b"ok\n"
            result = docker.run(["inspect", "literal;$(not-a-command)"], capture=True)
        self.assertEqual(result, "ok")
        self.assertEqual(run.call_args.args[0], ["docker", "inspect", "literal;$(not-a-command)"])
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_upgrade_starts_verified_controller_with_original_installation_mounts(self):
        docker = Docker(Locations())
        mounts = ("/config", "/data", "/state", "/var/run/docker.sock")
        docker.sources = {mount: "/host/install space" + mount for mount in mounts}
        docker.sources["/bundle"] = "/host/old release"
        value = manifest("v2.0.0")
        release = Release(value["version"], value["images"], value["database_major"])
        with patch.object(docker, "run") as run:
            docker.apply_upgrade(Path("/data/new bundle"), release, "v1.0.0")
        args = run.call_args.args[0]
        self.assertEqual(args[-2:], [release.images["installer"], "upgrade"])
        self.assertIn("ALGOTRADER_UPGRADE_FROM=v1.0.0", args)
        mounted = [args[i + 1] for i, arg in enumerate(args) if arg == "--mount"]
        self.assertCountEqual(
            mounted,
            [bind_mount(docker.sources[mount], mount) for mount in mounts]
            + [bind_mount("/host/install space/data/new bundle", "/bundle", readonly=True)],
        )
