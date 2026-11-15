"""Failed startup preserves diagnostics without replacing release checks."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release.smoke import report_failure, smoke
from release.tests.test_model import manifest


class SmokeTests(unittest.TestCase):
    def test_failed_startup_reports_before_cleanup_and_preserves_failure(self):
        events = []

        def command(args, **kwargs):
            if "up" in args:
                events.append("startup")
                raise RuntimeError("Redis exited before its first probe")
            if "down" in args:
                events.append("cleanup")

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "release.json"
            path.write_text(json.dumps(manifest("v0.0.1")))
            with (
                patch("release.smoke.verify_public"),
                patch("release.smoke.run", side_effect=command),
                patch("release.smoke.subprocess.run"),
                patch(
                    "release.smoke.report_failure",
                    side_effect=lambda _: events.append("diagnostics"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "Redis exited"):
                    smoke(path, "linux/arm64")
        self.assertEqual(events, ["startup", "diagnostics", "cleanup"])

    def test_missing_container_or_diagnostic_timeout_does_not_mask_failure(self):
        with patch(
            "release.smoke.subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 15)
        ) as run:
            report_failure("isolated-project")
        self.assertEqual(run.call_count, 10)
        commands = [item.args[0] for item in run.call_args_list]
        self.assertIn(
            ["docker", "inspect", "--format", "{{json .State}}", "isolated-project-redis-1"],
            commands,
        )
        self.assertIn(["docker", "logs", "--tail", "100", "isolated-project-redis-1"], commands)
