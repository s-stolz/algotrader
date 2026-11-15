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
                require_broker_market(broker_market() | fields, "123", "demo")

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


class BrokerMarketVerificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_acquisition_rechecks_current_instrument_even_after_successful_lookup(self):
        from unittest.mock import AsyncMock, Mock, patch

        from db_accessor_client.market_sources import BrokerMarketResolver

        market = broker_market()
        storage = Mock(get_market_by_id=AsyncMock(return_value=market))
        storage_context = Mock(
            __aenter__=AsyncMock(return_value=storage), __aexit__=AsyncMock(return_value=False)
        )
        broker = Mock(get=AsyncMock())
        broker_context = Mock(
            __aenter__=AsyncMock(return_value=broker), __aexit__=AsyncMock(return_value=False)
        )
        broker.get.side_effect = [
            Mock(json=Mock(return_value=market), raise_for_status=Mock()),
            Mock(
                json=Mock(return_value=market | {"broker_symbol_id": 99}), raise_for_status=Mock()
            ),
        ]
        resolver = BrokerMarketResolver("123", "demo")
        with (
            patch(
                "db_accessor_client.market_sources.AsyncDatabaseAccessorClient",
                return_value=storage_context,
            ),
            patch(
                "db_accessor_client.market_sources.httpx.AsyncClient", return_value=broker_context
            ),
        ):
            self.assertEqual(await resolver.resolve(1), market)
            with self.assertRaisesRegex(ValueError, "no longer matches"):
                await resolver.resolve(1)
        self.assertEqual(broker.get.await_count, 2)
        self.assertTrue(broker.get.call_args.args[0].endswith("/setup/instruments/10"))
        self.assertEqual(broker.get.call_args.kwargs["params"], {"account_id": "123"})

    async def test_every_basket_dependency_is_verified_against_current_broker_identity(self):
        from unittest.mock import AsyncMock, Mock, patch

        from db_accessor_client.market_sources import BrokerMarketResolver

        chart = broker_market()
        dependency = broker_market("USDJPY", symbol_id=2, broker_symbol_id=20)
        storage = Mock(get_markets=AsyncMock(return_value=[chart, dependency]))
        storage_context = Mock(
            __aenter__=AsyncMock(return_value=storage), __aexit__=AsyncMock(return_value=False)
        )
        broker = Mock(get=AsyncMock())
        broker_context = Mock(
            __aenter__=AsyncMock(return_value=broker), __aexit__=AsyncMock(return_value=False)
        )
        broker.get.side_effect = [
            Mock(json=Mock(return_value=chart), raise_for_status=Mock()),
            Mock(
                json=Mock(return_value=dependency | {"symbol": "RENAMED"}), raise_for_status=Mock()
            ),
        ]
        resolver = BrokerMarketResolver("123", "demo")
        with (
            patch(
                "db_accessor_client.market_sources.AsyncDatabaseAccessorClient",
                return_value=storage_context,
            ),
            patch(
                "db_accessor_client.market_sources.httpx.AsyncClient", return_value=broker_context
            ),
        ):
            with self.assertRaisesRegex(ValueError, "identity changed"):
                await resolver.dependencies(chart, ["EURUSD", "USDJPY"])
        self.assertEqual(broker.get.await_count, 2)

    async def test_status_subscription_can_resolve_stored_source_while_broker_is_offline(self):
        from unittest.mock import AsyncMock, Mock, patch

        from db_accessor_client.market_sources import BrokerMarketResolver

        market = broker_market()
        storage = Mock(get_market_by_id=AsyncMock(return_value=market))
        context = Mock(
            __aenter__=AsyncMock(return_value=storage), __aexit__=AsyncMock(return_value=False)
        )
        resolver = BrokerMarketResolver("123", "demo")
        with (
            patch(
                "db_accessor_client.market_sources.AsyncDatabaseAccessorClient",
                return_value=context,
            ),
            patch("db_accessor_client.market_sources.httpx.AsyncClient") as broker_http,
        ):
            self.assertEqual(await resolver.resolve_stored(1), market)
        broker_http.assert_not_called()
