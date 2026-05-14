import importlib
import unittest

MODULES = [
    "app",
    "app.backtest_runner",
    "app.config",
    "domain",
    "domain.enums",
    "domain.events",
    "domain.types",
    "execution",
    "execution.fills",
    "execution.portfolio",
    "execution.risk",
    "execution.sizing",
    "execution.trades",
    "engines",
    "engines.vectorized",
    "data",
    "data.feature_stream",
    "data.indicators",
    "data.market_data",
    "data.normalization",
    "data.warmup",
    "strategies",
    "strategies.base",
    "strategies.conditions",
    "strategies.examples",
    "strategies.examples.sma_crossover",
    "adapters",
    "adapters.db_accessor",
    "adapters.api",
    "adapters.api.routes",
    "cli",
    "reporting",
    "reporting.metrics",
]


class TestSkeletonImports(unittest.TestCase):
    def test_flattened_package_modules_import(self) -> None:
        for module_name in MODULES:
            with self.subTest(module=module_name):
                imported = importlib.import_module(module_name)
                self.assertIsNotNone(imported)


if __name__ == "__main__":
    unittest.main()
