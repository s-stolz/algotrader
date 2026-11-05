import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import python_environment as environment


class DependencyPolicyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "constraints-shared.txt").write_text("Foo_Bar==1.0\nother==2.0\n")
        (self.root / "service").mkdir()

    def override(self, text):
        (self.root / "service/constraints.override.txt").write_text(text)

    def test_override_replaces_shared_pin_without_losing_other_constraints(self):
        self.override("# Service needs the new API.\nfoo-bar==3.0\n")
        self.assertEqual(
            environment.effective_pins("service", self.root),
            {"foo-bar": "3.0", "other": "2.0"},
        )
        self.assertEqual(environment.effective_pins("root", self.root)["foo-bar"], "1.0")

    def test_default_service_uses_shared_versions(self):
        self.assertEqual(
            environment.effective_pins("service", self.root),
            {"foo-bar": "1.0", "other": "2.0"},
        )

    def test_ambiguous_or_unexplained_overrides_are_rejected(self):
        for content in (
            "foo-bar==3.0",
            "# Explanation\nunknown==1.0",
            "# Explanation\nfoo-bar>=1.0",
            "# Explanation\n-r another-file.txt",
            "# Explanation\nfoo-bar==3.0\n# Different name, same package\nFoo.Bar==4.0",
        ):
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.override(content)
                environment.effective_pins("service", self.root)

    def test_local_transitive_libraries_are_supplied_to_one_resolution(self):
        for directory, name, dependencies in (
            ("service", "service", '["local-client", "httpx>=1"]'),
            ("libs/client", "local-client", '["local-model"]'),
            ("libs/model", "local-model", "[]"),
        ):
            path = self.root / directory
            path.mkdir(parents=True, exist_ok=True)
            (path / "pyproject.toml").write_text(
                f'[project]\nname = "{name}"\ndependencies = {dependencies}\n'
            )
        arguments = environment.service_install_arguments("service", root=self.root)
        self.assertEqual(
            set(arguments[1::2]),
            {str(self.root / directory) for directory in ("service", "libs/client", "libs/model")},
        )
        dependency_arguments = environment.service_install_arguments(
            "service", root=self.root, dependencies_only=True
        )
        self.assertNotIn(str(self.root / "service"), dependency_arguments)
        self.assertIn("httpx>=1", dependency_arguments)

    def test_wrong_python_version_is_rejected(self):
        for version in ((3, 11), (3, 13)):
            with (
                self.subTest(version=version),
                patch.object(environment.sys, "version_info", version),
            ):
                with self.assertRaisesRegex(ValueError, "Python 3.12"):
                    environment.require_python312()

    def test_check_rejects_version_drift_even_if_pip_would_accept_it(self):
        with (
            patch.object(environment, "effective_pins", return_value={"httpx": "0.28.1"}),
            patch.object(environment.importlib.metadata, "version", return_value="0.27.0"),
            self.assertRaisesRegex(ValueError, "installed 0.27.0, expected 0.28.1"),
        ):
            environment.check("root")


if __name__ == "__main__":
    unittest.main()
