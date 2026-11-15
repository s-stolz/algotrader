import asyncio
import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Dict, cast

from app.domain.models import Symbol
from app.domain.value_objects import SymbolDescriptor, SymbolId
from app.infrastructure.ctrader_mappers import map_symbol_data
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAssetClassListReq,
    ProtoOAAssetClassListRes,
    ProtoOAAssetListReq,
    ProtoOAAssetListRes,
    ProtoOAErrorRes,
    ProtoOASymbolByIdReq,
    ProtoOASymbolByIdRes,
    ProtoOASymbolCategoryListReq,
    ProtoOASymbolCategoryListRes,
    ProtoOASymbolsListReq,
    ProtoOASymbolsListRes,
)

if TYPE_CHECKING:
    from typing import Awaitable, Callable

    from google.protobuf.message import Message

    SendRequestFn = Callable[[Message], Awaitable[Message]]
    AuthorizeFn = Callable[[int], Awaitable[None]]

logger = logging.getLogger(__name__)


class SymbolCache:
    """Manages symbol caching for cTrader client.

    Provides two levels of caching:
    - Light cache: Basic symbol info (name, id, enabled) from symbols list
    - Full cache: Detailed symbol info (digits, pip position, commission) from symbol by id
    """

    def __init__(self) -> None:
        # Light symbol cache: name -> SymbolDescriptor
        self._by_name: Dict[str, SymbolDescriptor] = {}
        # Light symbol cache: id -> SymbolDescriptor
        self._by_id: Dict[int, SymbolDescriptor] = {}
        # Full symbol cache: id -> Symbol (with digits, pip position, etc.)
        self._full_by_id: Dict[int, Symbol] = {}
        self._populate_lock = asyncio.Lock()
        self._metadata_lock = asyncio.Lock()
        self._assets: dict[int, str] | None = None
        self._categories: dict[int, str] | None = None

    @property
    def is_populated(self) -> bool:
        """Check if the light cache has been populated."""
        return bool(self._by_name)

    def get_by_name(self, name: str) -> SymbolDescriptor | None:
        """Get symbol descriptor by name."""
        return self._by_name.get(name)

    def get_by_id(self, symbol_id: int) -> SymbolDescriptor | None:
        """Get symbol descriptor by id."""
        return self._by_id.get(symbol_id)

    def get_full_by_id(self, symbol_id: int) -> Symbol | None:
        """Get full symbol info by id."""
        return self._full_by_id.get(symbol_id)

    def get_all_descriptors(self) -> list[SymbolDescriptor]:
        """Get all cached symbol descriptors sorted by name."""
        return sorted(self._by_name.values(), key=lambda s: s.symbol_name)

    def store_descriptor(self, descriptor: SymbolDescriptor) -> None:
        """Store a symbol descriptor in the cache."""
        self._by_name[descriptor.symbol_name] = descriptor
        self._by_id[descriptor.symbol_id] = descriptor

    def store_full_symbol(self, symbol: Symbol) -> None:
        """Store full symbol info in the cache."""
        self._full_by_id[symbol.symbol_id] = symbol

    async def ensure_populated(
        self,
        account_id: int,
        authorize_fn: "AuthorizeFn",
        send_request_fn: "SendRequestFn",
        *,
        force_refresh: bool = False,
    ) -> None:
        """Ensure the light symbol cache is populated.

        Fetches symbols list from API if cache is empty.
        """
        if self.is_populated and not force_refresh:
            return

        async with self._populate_lock:
            if self.is_populated and not force_refresh:
                return

            await authorize_fn(account_id)

            req = ProtoOASymbolsListReq(
                ctidTraderAccountId=account_id,
                includeArchivedSymbols=False,
            )
            res = await send_request_fn(req)
            if isinstance(res, ProtoOAErrorRes):
                error_res = cast(ProtoOAErrorRes, res)
                raise RuntimeError(
                    f"cTrader API error (code {error_res.errorCode}): {error_res.description}"
                )
            res = cast(ProtoOASymbolsListRes, res)

            self._by_name.clear()
            self._by_id.clear()
            for light in res.symbol:
                enabled = light.enabled if light.HasField("enabled") else None
                descriptor = SymbolDescriptor(
                    symbol_id=SymbolId(light.symbolId),
                    symbol_name=light.symbolName.upper(),
                    enabled=enabled,
                    quote_asset_id=light.quoteAssetId if light.HasField("quoteAssetId") else None,
                    category_id=(
                        light.symbolCategoryId if light.HasField("symbolCategoryId") else None
                    ),
                )
                self.store_descriptor(descriptor)

    async def get_or_fetch_symbol(
        self,
        account_id: int,
        name: str,
        authorize_fn: "AuthorizeFn",
        send_request_fn: "SendRequestFn",
    ) -> Symbol:
        """Get full symbol info, fetching from API if not cached.

        Args:
            account_id: The account ID for API requests.
            name: The symbol name (will be uppercased).
            authorize_fn: Function to authorize the account.
            send_request_fn: Function to send API requests.

        Returns:
            Full Symbol info with digits, pip position, etc.

        Raises:
            ValueError: If the symbol is unknown or not found.
        """
        name = name.upper()

        # Ensure light cache is populated first
        await self.ensure_populated(account_id, authorize_fn, send_request_fn)

        descriptor = self.get_by_name(name)
        if not descriptor:
            raise ValueError(f"Unknown symbol {name}")

        # Check full cache
        cached = self.get_full_by_id(descriptor.symbol_id)
        if cached is not None:
            return cached

        # Fetch detailed info from API
        req = ProtoOASymbolByIdReq(ctidTraderAccountId=account_id)
        req.symbolId.append(descriptor.symbol_id)
        res = await send_request_fn(req)
        if isinstance(res, ProtoOAErrorRes):
            error_res = cast(ProtoOAErrorRes, res)
            raise RuntimeError(
                f"cTrader API error (code {error_res.errorCode}): {error_res.description}"
            )
        res = cast(ProtoOASymbolByIdRes, res)

        if not res.symbol or res.symbol[0].symbolId != descriptor.symbol_id:
            raise ValueError(f"Symbol details not found for {name}")

        symbol = map_symbol_data(descriptor, res.symbol[0])
        self.store_full_symbol(symbol)

        return symbol

    async def enrich_metadata(
        self, account_id: int, symbol: Symbol, send_request_fn: "SendRequestFn"
    ) -> Symbol:
        try:
            async with self._metadata_lock:
                if self._assets is None:
                    assets = await send_request_fn(
                        ProtoOAAssetListReq(ctidTraderAccountId=account_id)
                    )
                    if not isinstance(assets, ProtoOAAssetListRes):
                        raise RuntimeError("Broker asset catalogue unavailable")
                    self._assets = {asset.assetId: asset.name for asset in assets.asset}
                if self._categories is None:
                    categories = await send_request_fn(
                        ProtoOASymbolCategoryListReq(ctidTraderAccountId=account_id)
                    )
                    classes = await send_request_fn(
                        ProtoOAAssetClassListReq(ctidTraderAccountId=account_id)
                    )
                    if not isinstance(categories, ProtoOASymbolCategoryListRes) or not isinstance(
                        classes, ProtoOAAssetClassListRes
                    ):
                        raise RuntimeError("Broker instrument classification unavailable")
                    class_names = {item.id: item.name for item in classes.assetClass}
                    self._categories = {
                        item.id: class_names.get(item.assetClassId, item.name)
                        for item in categories.symbolCategory
                    }
        except Exception:
            logger.warning("Optional instrument metadata unavailable for account=%s", account_id)
        descriptor = self.get_by_id(symbol.symbol_id)
        if descriptor is None:
            raise RuntimeError("Broker instrument is missing from its account catalogue")
        category = (self._categories or {}).get(descriptor.category_id or -1, "").casefold().strip()
        market_types = {
            "forex": "Forex",
            "fx": "Forex",
            "currencies": "Forex",
            "crypto": "Crypto",
            "cryptocurrency": "Crypto",
            "cryptocurrencies": "Crypto",
            "stocks": "Stock",
            "shares": "Stock",
            "equities": "Stock",
        }
        return replace(
            symbol,
            settlement_currency=(self._assets or {}).get(descriptor.quote_asset_id or -1),
            market_type=market_types.get(category),
        )

    def clear(self) -> None:
        """Clear all caches."""
        self._by_name.clear()
        self._by_id.clear()
        self._full_by_id.clear()
        self._assets = None
        self._categories = None
