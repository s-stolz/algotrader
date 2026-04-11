import importlib
import unittest

MODULES = [
    "app",
    "app.config",
    "domain",
    "domain.enums",
    "domain.events",
    "domain.types",
    "execution",
    "engines",
    "data",
    "strategies",
    "strategies.base",
    "adapters",
    "adapters.api",
    "adapters.api.routes",
    "reporting",
]


class TestSkeletonImports(unittest.TestCase):
    def test_flattened_package_modules_import(self) -> None:
        for module_name in MODULES:
            with self.subTest(module=module_name):
                imported = importlib.import_module(module_name)
                self.assertIsNotNone(imported)


if __name__ == "__main__":
    unittest.main()
