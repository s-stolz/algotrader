"""Release validation and persistence boundaries."""

import json
import tempfile
import unittest
from pathlib import Path

from release.installer.model import (
    IMAGE_NAMES,
    InstallationError,
    Release,
    protected_write,
    version_key,
)


def manifest(version="v1.0.0"):
    return {
        "schema_version": 1,
        "version": version,
        "database_major": 18,
        "images": {
            name: f"ghcr.io/example/algotrader-{name}@sha256:" + "a" * 64 for name in IMAGE_NAMES
        },
    }


class ReleaseTests(unittest.TestCase):
    def test_all_images_are_immutable_and_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "release.json"
            value = manifest("v1.0.0-alpha.1")
            path.write_text(json.dumps(value))
            self.assertEqual(Release.read(path).version, "v1.0.0-alpha.1")
            value["images"]["frontend"] = "ghcr.io/example/frontend:latest"
            path.write_text(json.dumps(value))
            with self.assertRaises(InstallationError):
                Release.read(path)

    def test_version_order_handles_numeric_prereleases_and_stable(self):
        versions = ["v1.0.0-alpha.2", "v1.0.0-alpha.10", "v1.0.0-beta.1", "v1.0.0", "v1.0.1"]
        self.assertEqual(sorted(reversed(versions), key=version_key), versions)
        with self.assertRaises(InstallationError):
            version_key("../../elsewhere")

    def test_secret_replacement_is_private_and_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "secrets.env"
            protected_write(path, "FIRST=secret\n")
            protected_write(path, "SECOND=changed\n")
            self.assertEqual(path.read_text(), "SECOND=changed\n")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(path.with_name(path.name + ".tmp").exists())
