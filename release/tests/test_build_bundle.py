"""Release gates prevent incomplete or private downloads from being published."""

import hashlib
import json
import posixpath
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from release.build_bundle import assemble, validate_tag, verify_public
from release.installer.model import InstallationError
from release.tests.test_model import manifest


class BundleTests(unittest.TestCase):
    def test_bundle_is_reproducible_and_pins_installer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            digests = root / "digests"
            digests.mkdir()
            value = manifest("v2.0.0-alpha.1")
            for name, image in value["images"].items():
                (digests / (name + ".json")).write_text(json.dumps({"name": name, "image": image}))
            first = assemble(value["version"], digests, root / "first")
            second = assemble(value["version"], digests, root / "second")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(
                    archive.read("installer-image.txt").decode().strip(),
                    value["images"]["installer"],
                )
                self.assertIn("SHA256SUMS", archive.namelist())
                for doc in ("operations.md", "recovery.md", "publishing.md"):
                    self.assertIn("docs/" + doc, archive.namelist())
                for line in archive.read("SHA256SUMS").decode().splitlines():
                    checksum, name = line.split("  ", 1)
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), checksum)
                for name in archive.namelist():
                    if not name.endswith(".md"):
                        continue
                    for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", archive.read(name).decode()):
                        if ":" in link or link.startswith("#"):
                            continue
                        target = posixpath.normpath(
                            posixpath.join(posixpath.dirname(name), link.split("#")[0])
                        )
                        self.assertIn(target, archive.namelist(), (name, link))

                self.assertEqual(archive.getinfo("algotrader.sh").external_attr >> 16, 0o100755)

    def test_missing_component_refuses_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(InstallationError, "incomplete"):
                assemble("v1.0.0", Path(folder), Path(folder) / "output")

    def test_main_ancestry_uses_literal_tag_argument(self):
        with patch("subprocess.run") as run:
            validate_tag("v1.0.0-alpha.1")
        self.assertEqual(
            run.call_args.args[0][-2:], ["refs/tags/v1.0.0-alpha.1^{commit}", "origin/main"]
        )
        with self.assertRaises(InstallationError):
            validate_tag("v1.0.0;echo bad")

    def test_anonymous_gate_uses_empty_credentials_and_fails_private_package(self):
        with patch("subprocess.run", return_value=Mock(returncode=1)) as run:
            with self.assertRaisesRegex(InstallationError, "visibility to Public"):
                verify_public(manifest()["images"])
            docker_config = Path(run.call_args.kwargs["env"]["DOCKER_CONFIG"])
            self.assertNotEqual(str(docker_config), str(Path.home() / ".docker"))
