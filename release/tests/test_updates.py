"""Published release selection and verified bundle handoff."""

import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

from release.installer import updates
from release.installer.model import InstallationError
from release.tests.test_model import manifest


class ReleaseDiscoveryTests(unittest.TestCase):
    def test_stable_uses_published_latest_endpoint(self):
        tag = "v1.2.3"
        payload = json.dumps({"tag_name": tag, "prerelease": False, "draft": False}).encode()
        with patch.object(updates, "read_url", return_value=payload) as read:
            self.assertEqual(updates.latest_version(False), tag)
        self.assertEqual(
            read.call_args.args[0],
            "https://api.github.com/repos/s-stolz/algotrader/releases/latest",
        )

    def test_stable_discovery_rejects_ineligible_releases(self):
        for entry in [
            {"tag_name": "v1.2.3", "draft": True},
            {"tag_name": "v1.2.3", "prerelease": True},
            {"tag_name": "v1.2.3-alpha.1", "prerelease": False},
            {"tag_name": "experimental"},
        ]:
            with (
                self.subTest(entry=entry),
                patch.object(updates, "read_url", return_value=json.dumps(entry).encode()),
            ):
                with self.assertRaises(InstallationError):
                    updates.latest_version(False)

    def test_prereleases_are_ordered_by_version_across_pages(self):
        first = [{"tag_name": "v1.2.2"}, {"tag_name": "v1.2.3-alpha.2"}]
        first.extend([{"tag_name": "v3.0.0", "draft": True}] * 98)
        second = [
            {"tag_name": "v1.2.3-alpha.10", "prerelease": True},
            {"tag_name": "not-a-release"},
        ]
        with patch.object(
            updates,
            "read_url",
            side_effect=[json.dumps(first).encode(), json.dumps(second).encode()],
        ) as read:
            self.assertEqual(updates.latest_version(True), "v1.2.3-alpha.10")
        self.assertEqual(
            [call.args[0] for call in read.call_args_list],
            [f"{updates.API}?per_page=100&page={page}" for page in (1, 2)],
        )

    def test_offline_github_returns_an_actionable_failure(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            with self.assertRaisesRegex(InstallationError, "offline"):
                updates.latest_version(False)


class BundleDownloadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.version = "v2.0.0"
        self.value = manifest(self.version)
        self.image = self.value["images"]["installer"]
        self.files = {
            "release.json": json.dumps(self.value),
            "installer-image.txt": self.image + "\n",
            "compose.yaml": "services: {}\n",
        }

    def serve_bundle(self, checksum=None, filename="algotrader-v2.0.0.zip"):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, content in self.files.items():
                archive.writestr(name, content)
        bundle = buffer.getvalue()
        digest = checksum or hashlib.sha256(bundle).hexdigest()
        return patch.object(
            updates, "read_url", side_effect=[f"{digest}  {filename}\n".encode(), bundle]
        )

    def test_matching_checksum_manifest_and_image_handoff(self):
        with self.serve_bundle() as read:
            release = updates.download_bundle(self.version, self.directory)
        self.assertEqual(release.version, self.version)
        self.assertEqual(release.images["installer"], self.image)
        self.assertEqual((self.directory / "compose.yaml").read_text(), self.files["compose.yaml"])
        url = "https://github.com/s-stolz/algotrader/releases/download/v2.0.0/algotrader-v2.0.0.zip"
        self.assertEqual([call.args[0] for call in read.call_args_list], [url + ".sha256", url])

    def test_checksum_file_must_name_selected_bundle(self):
        with (
            self.serve_bundle(filename="unrelated.zip") as read,
            self.assertRaises(InstallationError),
        ):
            updates.download_bundle(self.version, self.directory)
        self.assertEqual(read.call_count, 1)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_changed_archive_rejected_before_extraction(self):
        with self.serve_bundle(checksum="0" * 64), self.assertRaises(InstallationError):
            updates.download_bundle(self.version, self.directory)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_archive_manifest_must_name_selected_version(self):
        self.files["release.json"] = json.dumps(manifest("v1.0.0"))
        with self.serve_bundle(), self.assertRaises(InstallationError):
            updates.download_bundle(self.version, self.directory)

    def test_archive_controller_image_must_match_pinned_manifest(self):
        self.files["installer-image.txt"] = "ghcr.io/example/installer@sha256:" + "b" * 64
        with self.serve_bundle(), self.assertRaises(InstallationError):
            updates.download_bundle(self.version, self.directory)
