"""Native launcher argument handling without a Docker daemon."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from release.tests.test_model import manifest

ROOT = Path(__file__).resolve().parents[2]


class LauncherContract:
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.bundle = self.root / "release bundle"
        self.bundle.mkdir()
        self.target = self.root / "user's installation"
        self.log = self.root / "run.json"
        self.installer = "ghcr.io/example/installer@sha256:" + "a" * 64
        self.write_bundle(self.bundle, "v1.0.0", self.installer)
        self.save_installed_version("v1.0.0", self.installer)

    def write_bundle(self, folder, version, image):
        data = manifest(version)
        data["images"]["installer"] = image
        (folder / "release.json").write_text(json.dumps(data, indent=2) + "\n")
        (folder / "installer-image.txt").write_text(image + "\n")

    def save_installed_version(self, version, image):
        data = self.target / "data" / "releases" / version
        data.mkdir(parents=True, exist_ok=True)
        self.write_bundle(data, version, image)
        state = self.target / "state"
        state.mkdir(parents=True, exist_ok=True)
        (state / "installation.json").write_text(
            json.dumps({"version": version, "project": "algotrader-123456abcdef"}, indent=2)
        )

    def docker_args(self, *args):
        self.log.unlink(missing_ok=True)
        result = self.run_launcher(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(self.log.read_text(encoding="utf-8-sig"))

    def test_installed_launcher_discovers_stable_or_opts_in_to_prereleases(self):
        for options, expected in [
            ([], ["update"]),
            ([self.prerelease], ["update", "--prerelease"]),
        ]:
            with self.subTest(options=options):
                args = self.docker_args("upgrade", *options)
                self.assertEqual(args[-len(expected) - 1 :], [self.installer, *expected])
                self.assertIn(str(self.target / "config") + ":/config", args)

    def test_downloaded_bundle_bootstraps_legacy_installation(self):
        newer = "ghcr.io/example/installer@sha256:" + "b" * 64
        self.write_bundle(self.bundle, "v2.0.0", newer)
        (self.target / "data/releases/v1.0.0/installer-image.txt").unlink()
        args = self.docker_args("upgrade", self.from_bundle)
        self.assertEqual(args[-2:], [newer, "apply-bundle"])
        self.assertIn(str(self.bundle) + ":/bundle:ro", args)

    def test_original_launcher_follows_installed_controller_after_upgrade(self):
        newer = "ghcr.io/example/installer@sha256:" + "b" * 64
        self.save_installed_version("v2.0.0", newer)
        self.assertEqual(self.docker_args("status")[-2:], [newer, "status"])
        self.assertEqual(self.docker_args("upgrade")[-2:], [newer, "update"])

    def test_conflicting_upgrade_options_do_not_invoke_controller(self):
        result = self.run_launcher("upgrade", self.prerelease, self.from_bundle)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())


class LauncherTests(LauncherContract, unittest.TestCase):
    prerelease = "--prerelease"
    from_bundle = "--from-bundle"

    def setUp(self):
        super().setUp()
        shutil.copy(ROOT / "release/algotrader.sh", self.bundle)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        fake = self.bin_dir / "docker"
        fake.write_text("""#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args[:2] == ["info", "--format"]:
    print("linux")
elif args[:2] == ["compose", "version"]:
    print("2.39.4-desktop.1")
elif args[:2] == ["context", "inspect"]:
    print("unix:///var/run/docker.sock")
elif args[0] == "run":
    open(os.environ["LAUNCHER_TEST_LOG"], "w").write(json.dumps(args))
""")
        fake.chmod(0o755)

    def run_launcher(self, command, *options):
        return subprocess.run(
            [
                "bash",
                str(self.bundle / "algotrader.sh"),
                command,
                "--directory",
                str(self.target),
                *options,
            ],
            cwd=self.root,
            env={
                **os.environ,
                "PATH": str(self.bin_dir) + os.pathsep + os.environ["PATH"],
                "DOCKER_HOST": "",
                "LAUNCHER_TEST_LOG": str(self.log),
            },
            capture_output=True,
            text=True,
        )

    def test_shell_preserves_installation_paths_and_does_not_evaluate_them(self):
        self.target = self.root / 'spaces and "quotes" $(touch unwanted)'
        self.save_installed_version("v1.0.0", self.installer)
        args = self.docker_args("status")
        self.assertIn(str(self.target / "config") + ":/config", args)
        self.assertEqual(args[-1], "status")
        self.assertFalse((self.root / "unwanted").exists())


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell is required")
class PowerShellLauncherTests(LauncherContract, unittest.TestCase):
    prerelease = "-Prerelease"
    from_bundle = "-FromBundle"

    def setUp(self):
        super().setUp()
        shutil.copy(ROOT / "release/algotrader.ps1", self.bundle)
        self.driver = self.root / "run-launcher.ps1"
        self.driver.write_text("""param(
    [string]$Launcher, [string]$Target, [string]$Command,
    [switch]$Prerelease, [switch]$FromBundle
)
function docker {
    $global:LASTEXITCODE = 0
    switch ($args[0]) {
        'info' { if ($args -contains '--format') { 'linux' } }
        'context' { 'npipe:////./pipe/docker_engine' }
        'compose' { '2.39.4-desktop.1' }
        'run' {
            ConvertTo-Json -Compress -InputObject $args |
                Set-Content -LiteralPath $env:LAUNCHER_TEST_LOG -Encoding utf8
        }
        default { throw "Unexpected Docker command $args" }
    }
}
$options = @{}
if ($Prerelease) { $options.Prerelease = $true }
if ($FromBundle) { $options.FromBundle = $true }
& $Launcher $Command -Directory $Target @options
exit $LASTEXITCODE
""")

    def run_launcher(self, command, *options):
        return subprocess.run(
            [
                "pwsh",
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(self.driver),
                str(self.bundle / "algotrader.ps1"),
                str(self.target),
                command,
                *options,
            ],
            cwd=self.root,
            env={**os.environ, "DOCKER_HOST": "", "LAUNCHER_TEST_LOG": str(self.log)},
            capture_output=True,
            text=True,
        )
