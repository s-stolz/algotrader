from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.domain.models import Symbol
from app.domain.value_objects import SymbolDescriptor, SymbolId
from app.infrastructure.ctrader_client import CtraderClient
from app.infrastructure.ctrader_mappers import map_symbol_data
from app.infrastructure.ctrader_symbol_cache import SymbolCache
from app.settings import CtraderCredentials
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAssetClassListRes,
    ProtoOAAssetListRes,
    ProtoOASymbolCategoryListRes,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOASymbol


class CatalogueTests(unittest.IsolatedAsyncioTestCase):
    def test_client_never_reuses_another_accounts_instrument_mapping(self) -> None:
        credentials = CtraderCredentials(
            "id", "secret", "demo", "a", "r", "https://example.com", 60, 10
        )
        with patch.object(CtraderClient, "_create_client"):
            client = CtraderClient(credentials)
        first = client._symbol_cache_for(1)
        second = client._symbol_cache_for(2)
        first.store_descriptor(SymbolDescriptor(SymbolId(10), "EURUSD"))
        second.store_descriptor(SymbolDescriptor(SymbolId(20), "EURUSD"))
        first_symbol = first.get_by_name("EURUSD")
        second_symbol = second.get_by_name("EURUSD")
        assert first_symbol is not None and second_symbol is not None
        self.assertEqual(first_symbol.symbol_id, 10)
        self.assertEqual(second_symbol.symbol_id, 20)
        self.assertIsNone(second.get_by_id(10))

    def test_mapper_exposes_valid_timezone_and_volume_units(self) -> None:
        symbol = map_symbol_data(
            SymbolDescriptor(SymbolId(1), "EURUSD"),
            ProtoOASymbol(
                symbolId=1,
                digits=5,
                pipPosition=4,
                scheduleTimeZone="Europe/London",
                minVolume=100,
                stepVolume=50,
                lotSize=10000000,
            ),
        )
        self.assertEqual(symbol.timezone, "Europe/London")
        self.assertEqual(symbol.minimum_quantity, 1)
        self.assertEqual(symbol.quantity_step, 0.5)
        self.assertEqual(symbol.lot_size, 100000)

    async def test_quote_asset_and_asset_class_are_joined_for_selected_instrument(self) -> None:
        cache = SymbolCache()
        cache.store_descriptor(
            SymbolDescriptor(SymbolId(1), "EURUSD", True, quote_asset_id=2, category_id=3)
        )
        assets = ProtoOAAssetListRes(ctidTraderAccountId=1)
        assets.asset.add(assetId=2, name="USD")
        categories = ProtoOASymbolCategoryListRes(ctidTraderAccountId=1)
        categories.symbolCategory.add(id=3, assetClassId=4, name="Majors")
        classes = ProtoOAAssetClassListRes(ctidTraderAccountId=1)
        classes.assetClass.add(id=4, name="Forex")
        send = AsyncMock(side_effect=[assets, categories, classes])
        symbol = await cache.enrich_metadata(1, Symbol(1, "EURUSD", 5, 4), send)
        self.assertEqual(symbol.settlement_currency, "USD")
        self.assertEqual(symbol.market_type, "Forex")
        await cache.enrich_metadata(1, Symbol(1, "EURUSD", 5, 4), send)
        self.assertEqual(send.await_count, 3)

    async def test_optional_metadata_failure_preserves_verified_identity(self) -> None:
        cache = SymbolCache()
        cache.store_descriptor(SymbolDescriptor(SymbolId(1), "EURUSD"))
        symbol = await cache.enrich_metadata(
            1, Symbol(1, "EURUSD", 5, 4), AsyncMock(side_effect=RuntimeError("unavailable"))
        )
        self.assertEqual(symbol.symbol_id, 1)
        self.assertIsNone(symbol.settlement_currency)
        self.assertIsNone(symbol.market_type)
