"""Registration invariants at the same catalog seam used by defaults and API."""

import unittest
from dataclasses import replace

from indicator_engine.builtin_catalog import BUILTIN_CATALOG
from indicator_engine.catalog import IndicatorCatalog, IndicatorRegistration
from indicator_engine.indicators.sma import SMA


class IndicatorCatalogTests(unittest.TestCase):
    def setUp(self):
        self.entry = IndicatorRegistration(
            public_id=42,
            implementation=SMA,
            supports_live=True,
            overlay=True,
            outputs={"sma": {"type": "line", "plotOptions": {"color": "red"}}},
        )

    def test_rejects_duplicate_public_or_engine_identity(self):
        class Other(SMA):
            def __init__(self):
                super().__init__()
                self.spec = replace(self.spec, id="other")

        for duplicate in (
            replace(self.entry, implementation=Other),
            replace(self.entry, public_id=43),
        ):
            with self.subTest(duplicate=duplicate), self.assertRaises(ValueError):
                IndicatorCatalog([self.entry, duplicate])

    def test_rejects_invalid_registration_configuration(self):
        invalid = (
            {"public_id": True},
            {"public_id": 0},
            {"public_id": "42"},
            {"supports_live": None},
            {"overlay": 1},
            {"implementation": object()},
            {"outputs": {"missing": {"type": "line"}}},
            {"outputs": {"sma": {}}},
            {"outputs": {"sma": {"type": ""}}},
            {"outputs": {"sma": {"type": "line", "plotOptions": []}}},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                IndicatorCatalog([replace(self.entry, **changes)])

    def test_default_registry_contains_every_catalog_implementation(self):
        from indicator_engine import get_registry

        registry = get_registry()
        for entry in BUILTIN_CATALOG:
            self.assertEqual(registry.get(entry.engine_id).spec, entry.implementation().spec)

    def test_registry_instances_are_independent(self):
        catalog = IndicatorCatalog([self.entry])
        first = catalog.create_registry()
        second = catalog.create_registry()
        self.assertIsNot(first.get("sma"), second.get("sma"))
        self.assertEqual(first.get("sma").spec, second.get("sma").spec)
