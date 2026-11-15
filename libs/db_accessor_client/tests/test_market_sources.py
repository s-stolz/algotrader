import unittest
from typing import Any

from db_accessor_client.market_sources import (
    require_broker_market,
    resolve_broker_dependencies,
)


def broker_market(symbol: str = "EURUSD", **overrides: Any):
    return {
        "symbol_id": 1,
        "symbol": symbol,
        "exchange": "BROKER",
        "source_type": "broker",
        "broker_provider": "ctrader",
        "broker_account_id": "123",
        "broker_environment": "demo",
        "broker_symbol_id": 10,
        **overrides,
    }


class BrokerMarketTests(unittest.TestCase):
    def test_custom_same_symbol_never_becomes_a_live_input(self):
        custom = broker_market(source_type="custom")
        with self.assertRaisesRegex(ValueError, "Custom markets"):
            require_broker_market(custom, "123", "demo")
        with self.assertRaisesRegex(ValueError, "requires one"):
            resolve_broker_dependencies([custom], ["EURUSD"], broker_market(), "123", "demo")

    def test_provider_account_and_environment_must_match(self):
        for fields in (
            {"broker_provider": "other"},
            {"broker_account_id": "456"},
            {"broker_environment": "live"},
            {"broker_symbol_id": None},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                require_broker_market(broker_market(**fields), "123", "demo")

    def test_dependencies_use_same_exchange_and_reject_missing_or_ambiguous_sources(self):
        chart = broker_market()
        source = broker_market("USDJPY", symbol_id=2, broker_symbol_id=20)
        other = broker_market("USDJPY", symbol_id=3, exchange="CSV", source_type="custom")
        self.assertEqual(
            resolve_broker_dependencies([source, other], ["USDJPY"], chart, "123", "demo"),
            [source],
        )
        for sources in ([other], [source, source]):
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                resolve_broker_dependencies(sources, ["USDJPY"], chart, "123", "demo")
