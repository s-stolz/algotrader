"""Release runtime checks execute on matching native architectures."""

import unittest

import yaml

from release.smoke import ROOT


class WorkflowTests(unittest.TestCase):
    def test_runtime_checks_use_matching_native_runners(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
        job = workflow["jobs"]["smoke"]
        self.assertEqual(job["runs-on"], "${{ matrix.runner }}")
        self.assertEqual(
            job["strategy"]["matrix"]["include"],
            [
                {"platform": "linux/amd64", "runner": "ubuntu-latest"},
                {"platform": "linux/arm64", "runner": "ubuntu-24.04-arm"},
            ],
        )
        self.assertFalse(any("setup-qemu" in step.get("uses", "") for step in job["steps"]))
        self.assertTrue(any("release.smoke" in step.get("run", "") for step in job["steps"]))
