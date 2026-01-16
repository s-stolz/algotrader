import logging
from typing import TYPE_CHECKING, Dict, cast

from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOASymbolByIdReq,
    ProtoOASymbolByIdRes,
    ProtoOASymbolsListReq,
    ProtoOASymbolsListRes,
)

from app.domain.models import Symbol
from app.domain.value_objects import SymbolDescriptor, SymbolId
from app.infrastructure.ctrader_mappers import map_symbol_data

if TYPE_CHECKING:
    from google.protobuf.message import Message
    from typing import Awaitable, Callable

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
    ) -> None:
        """Ensure the light symbol cache is populated.

        Fetches symbols list from API if cache is empty.
        """
        if self.is_populated:
            return

        await authorize_fn(account_id)

        req = ProtoOASymbolsListReq(
            ctidTraderAccountId=account_id,
            includeArchivedSymbols=False,
        )
        res = cast(ProtoOASymbolsListRes, await send_request_fn(req))

        for light in res.symbol:
            enabled = getattr(light, "enabled", None)
            descriptor = SymbolDescriptor(
                symbol_id=SymbolId(light.symbolId),
                symbol_name=light.symbolName.upper(),
                enabled=enabled,
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
        res = cast(ProtoOASymbolByIdRes, await send_request_fn(req))

        if not res.symbol:
            raise ValueError(f"Symbol details not found for {name}")

        symbol = map_symbol_data(descriptor, res.symbol[0])
        self.store_full_symbol(symbol)

        return symbol

    async def get_light_symbol(
        self,
        account_id: int,
        name: str,
        authorize_fn: "AuthorizeFn",
        send_request_fn: "SendRequestFn",
    ) -> SymbolDescriptor:
        """Get light symbol info (descriptor only).

        Args:
            account_id: The account ID for API requests.
            name: The symbol name (will be uppercased).
            authorize_fn: Function to authorize the account.
            send_request_fn: Function to send API requests.

        Returns:
            SymbolDescriptor with basic symbol info.

        Raises:
            ValueError: If the symbol is unknown.
        """
        name = name.upper()
        await self.ensure_populated(account_id, authorize_fn, send_request_fn)

        descriptor = self.get_by_name(name)
        if not descriptor:
            raise ValueError(f"Unknown symbol {name}")

        return descriptor

    def clear(self) -> None:
        """Clear all caches."""
        self._by_name.clear()
        self._by_id.clear()
        self._full_by_id.clear()
