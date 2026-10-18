"""Topology history policy reaches runtime without ambiguous boundaries."""

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("generate_env", ROOT / "scripts/generate_env.py")
assert spec is not None and spec.loader is not None
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class HistoryMappingTests(unittest.TestCase):
    def test_default_and_date_mapping_and_invalid_policies(self):
        original = generator.read_yaml(ROOT / "config/topology.yaml")
        shared, *_ = generator.build_env(original, {})
        self.assertEqual(shared["HISTORY_LOOKBACK_DAYS"], "1825")
        self.assertEqual(shared["HISTORY_START_DATE"], "")
        topology = copy.deepcopy(original)
        topology["ingestion"].update(lookback_days=None, start_date="2026-10-05")
        shared, *_ = generator.build_env(topology, {})
        self.assertEqual(shared["HISTORY_LOOKBACK_DAYS"], "")
        self.assertEqual(shared["HISTORY_START_DATE"], "2026-10-05")
        for days, date in [
            (None, None),
            (1, "2026-10-05"),
            (0, None),
            (True, None),
            (None, "not-a-date"),
        ]:
            topology = copy.deepcopy(original)
            topology["ingestion"].update(lookback_days=days, start_date=date)
            with self.assertRaises(ValueError):
                generator.build_env(topology, {})
