"""Native launcher argument handling without a Docker daemon."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class LauncherTests(unittest.TestCase):
    def test_shell_preserves_installation_paths_and_does_not_evaluate_them(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle = root / "release bundle"
            bundle.mkdir()
            (bundle / "algotrader.sh").write_bytes((ROOT / "release/algotrader.sh").read_bytes())
            (bundle / "release.json").write_text("{}")
            (bundle / "installer-image.txt").write_text(
                "ghcr.io/example/installer@sha256:" + "a" * 64 + "\n"
            )
            bin_dir = root / "bin"
            bin_dir.mkdir()
            log = root / "args.json"
            fake = bin_dir / "docker"
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
            target = root / 'spaces and "quotes" $(touch unwanted)'
            environment = {
                **os.environ,
                "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                "LAUNCHER_TEST_LOG": str(log),
            }
            subprocess.run(
                ["bash", str(bundle / "algotrader.sh"), "status", "--directory", str(target)],
                env=environment,
                check=True,
                capture_output=True,
            )
            args = json.loads(log.read_text())
            self.assertIn(str(target / "config") + ":/config", args)
            self.assertIn(str(bundle) + ":/bundle:ro", args)
            self.assertEqual(args[-1], "status")
            self.assertFalse((root / "unwanted").exists())
