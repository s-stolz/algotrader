import asyncio
import logging
import threading
import uuid
from typing import Any, Awaitable, Callable, Dict, Tuple, cast

from ctrader_open_api import Client, Protobuf, TcpProtocol
from ctrader_open_api.endpoints import EndPoints
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAAccountAuthRes,
    ProtoOAAccountLogoutReq,
    ProtoOAApplicationAuthReq,
    ProtoOAApplicationAuthRes,
    ProtoOACancelOrderReq,
    ProtoOAClosePositionReq,
    ProtoOADealListReq,
    ProtoOADealListRes,
    ProtoOAErrorRes,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetAccountListByAccessTokenRes,
    ProtoOAGetTrendbarsReq,
    ProtoOAGetTrendbarsRes,
    ProtoOANewOrderReq,
    ProtoOAOrderListReq,
    ProtoOAOrderListRes,
    ProtoOAReconcileReq,
    ProtoOAReconcileRes,
    ProtoOASpotEvent,
    ProtoOASubscribeLiveTrendbarReq,
    ProtoOASubscribeSpotsReq,
    ProtoOATraderReq,
    ProtoOATraderRes,
    ProtoOAUnsubscribeLiveTrendbarReq,
    ProtoOAUnsubscribeSpotsReq,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
    ProtoOATrendbarPeriod,
    ProtoOAOrderType,
    ProtoOATradeSide,
    ProtoOATimeInForce,
)
from google.protobuf.message import Message
from twisted.internet import reactor
from twisted.internet.defer import Deferred

from app.application.interfaces import BrokerPort, MarketDataPort
from app.domain.models import (
    Account,
    Deal,
    Order,
    Position,
    Symbol,
    Tick,
    Trendbar
)
from app.domain.value_objects import (
    AccountId,
    OrderId,
    PositionId,
    SymbolDescriptor,
    SymbolId,
    Timeframe,
)
from app.infrastructure.ctrader_mappers import (
    map_deal,
    map_order,
    map_position,
    map_tick,
    map_trader,
    map_trendbar,
    resolve_timeframe,
)
from app.infrastructure.ctrader_symbol_cache import SymbolCache
from app.infrastructure.stream_registry import (
    TickSubscription,
    TrendbarSubscription,
)
from app.settings import CtraderCredentials

logger = logging.getLogger(__name__)

TickHandler = Callable[[Tick], Awaitable[None]]
TrendbarHandler = Callable[[Trendbar], Awaitable[None]]


class CtraderClient(BrokerPort, MarketDataPort):
    """Async wrapper that keeps Twisted reactor in a background thread."""

    def __init__(
        self,
        credentials: CtraderCredentials,
        request_timeout: float = 5.0
    ) -> None:
        self._credentials = credentials
        self._request_timeout = max(1.0, float(request_timeout))

        # Twisted client setup
        self._client = self._create_client(credentials)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._reactor_thread: threading.Thread | None = None

        # Authentication state
        self._app_authenticated = asyncio.Event()
        self._authorized_accounts: set[int] = set()

        # Shutdown state
        self._shutting_down = False

        # Symbol cache
        self._symbol_cache = SymbolCache()

        # Tick streaming state
        self._tick_handlers: Dict[
            Tuple[int, int],
            Dict[str, TickHandler]
        ] = {}
        self._tick_lock = asyncio.Lock()
        self._active_tick_streams: set[Tuple[int, int]] = set()

        # Trendbar streaming state (key: account_id, symbol_id, timeframe)
        self._trendbar_handlers: Dict[
            Tuple[int, int, str],
            Dict[str, TrendbarHandler]
        ] = {}
        self._trendbar_lock = asyncio.Lock()
        self._active_trendbar_streams: set[Tuple[int, int, str]] = set()

    def _create_client(self, credentials: CtraderCredentials) -> Client:
        """Create and configure the Twisted client."""
        endpoint = (
            EndPoints.PROTOBUF_LIVE_HOST
            if credentials.host_type.lower() == "live"
            else EndPoints.PROTOBUF_DEMO_HOST
        )
        client = Client(endpoint, EndPoints.PROTOBUF_PORT, TcpProtocol)
        client.setConnectedCallback(self._on_connected)
        client.setDisconnectedCallback(self._on_disconnected)
        client.setMessageReceivedCallback(self._on_message)
        return client

    # ------------------------------------------------------------- lifecycle

    async def connect(self) -> None:
        if self._reactor_thread:
            return
        self._loop = asyncio.get_running_loop()
        self._reactor_thread = threading.Thread(
            target=self._start_reactor, daemon=True)
        self._reactor_thread.start()
        await self._app_authenticated.wait()

    async def disconnect(self) -> None:
        self._shutting_down = True
        for account_id in list(self._authorized_accounts):
            try:
                await self._send_request(
                    ProtoOAAccountLogoutReq(ctidTraderAccountId=account_id)
                )
            except Exception:
                logger.exception("Failed to logout account %s", account_id)
        if reactor.running:  # type: ignore[attr-defined]
            reactor.callFromThread(reactor.stop)  # type: ignore[attr-defined]
        if self._reactor_thread:
            self._reactor_thread.join(timeout=2)
            self._reactor_thread = None

    @property
    def is_connected(self) -> bool:
        return self._app_authenticated.is_set()

    # ------------------------------------------------------------- BrokerPort

    async def list_accounts(self) -> list[Account]:
        res = cast(
            ProtoOAGetAccountListByAccessTokenRes,
            await self._send_request(
                ProtoOAGetAccountListByAccessTokenReq(
                    accessToken=self._credentials.access_token)
            ),
        )
        accounts: list[Account] = []
        is_live_host = self._credentials.host_type == "live"
        for entry in res.ctidTraderAccount:
            # Skip accounts that don't match the current host type
            if entry.isLive != is_live_host:
                continue

            trader = await self._get_trader(entry.ctidTraderAccountId)
            accounts.append(map_trader(trader, is_live=entry.isLive))
        return accounts

    async def get_open_orders(self, account_id: AccountId) -> list[Order]:
        data = await self._reconcile(account_id)
        return [
            map_order(order, self._symbol_cache.get_by_id)
            for order in data.order
        ]

    async def get_order_history(
        self,
        account_id: AccountId,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> list[Order]:
        await self._authorize_account(int(account_id))

        req = ProtoOAOrderListReq(
            ctidTraderAccountId=int(account_id),
            fromTimestamp=from_ts or 0,
            toTimestamp=to_ts or 2147483646000,
        )

        res = await self._send_request(req)

        if isinstance(res, ProtoOAErrorRes):
            error_res = cast(ProtoOAErrorRes, res)
            raise RuntimeError(
                f"cTrader API error (code {error_res.errorCode}): {error_res.description}"
            )

        res = cast(ProtoOAOrderListRes, res)
        return [
            map_order(order, self._symbol_cache.get_by_id)
            for order in res.order
        ]

    async def place_order(
        self,
        account_id: AccountId,
        payload: dict
    ) -> dict[str, Any]:
        symbol = payload["symbol"].upper()
        info = await self._get_symbol(int(account_id), symbol)
        req = ProtoOANewOrderReq(ctidTraderAccountId=int(account_id))
        req.symbolId = info.symbol_id
        req.orderType = ProtoOAOrderType.Value(payload["orderType"].upper())
        req.tradeSide = ProtoOATradeSide.Value(payload["tradeSide"].upper())
        req.volume = int(payload["volume"])
        if "limitPrice" in payload:
            req.limitPrice = float(payload["limitPrice"])
        if "stopPrice" in payload:
            req.stopPrice = float(payload["stopPrice"])
        if "stopLoss" in payload:
            req.stopLoss = float(payload["stopLoss"])
        if "takeProfit" in payload:
            req.takeProfit = float(payload["takeProfit"])
        if "timeInForce" in payload:
            req.timeInForce = ProtoOATimeInForce.Value(
                payload["timeInForce"].upper())
        if "expirationTimestamp" in payload:
            req.expirationTimestamp = int(payload["expirationTimestamp"])
        if payload.get("comment"):
            req.comment = payload["comment"]
        if payload.get("label"):
            req.label = payload["label"]
        if payload.get("clientOrderId"):
            req.clientOrderId = payload["clientOrderId"]
        await self._send_request(req)

        return {
            "status": "submitted",
            "symbol": symbol,
            "volume": req.volume,
        }

    async def cancel_order(
        self,
        account_id: AccountId,
        order_id: OrderId
    ) -> None:
        req = ProtoOACancelOrderReq(
            ctidTraderAccountId=int(account_id),
            orderId=int(order_id),
        )
        await self._send_request(req)

    async def get_open_positions(self, account_id: AccountId) -> list[Position]:
        data = await self._reconcile(account_id)
        return [
            map_position(pos, self._symbol_cache.get_by_id)
            for pos in data.position
        ]

    async def get_deal_history(
        self,
        account_id: AccountId,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> list[Deal]:
        await self._authorize_account(int(account_id))

        req = ProtoOADealListReq(
            ctidTraderAccountId=int(account_id),
            fromTimestamp=from_ts or 0,
            toTimestamp=to_ts or 2147483646000,
        )

        res = await self._send_request(req)

        if isinstance(res, ProtoOAErrorRes):
            error_res = cast(ProtoOAErrorRes, res)
            raise RuntimeError(
                f"cTrader API error (code {error_res.errorCode}): {error_res.description}"
            )

        res = cast(ProtoOADealListRes, res)
        return [
            map_deal(deal, self._symbol_cache.get_by_id)
            for deal in res.deal
        ]

    async def close_position(
        self,
        account_id: AccountId,
        position_id: PositionId,
        close_volume: int | None = None,
    ) -> dict[str, Any]:
        req = ProtoOAClosePositionReq(ctidTraderAccountId=int(
            account_id), positionId=int(position_id))
        if close_volume:
            req.volume = int(close_volume)
        await self._send_request(req)

        return {
            "status": "close-requested",
            "positionId": int(position_id),
        }

    # ---------------------------------------------------------- MarketDataPort

    async def get_trendbars(
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        from_ts: int,
        to_ts: int | None,
        limit: int | None,
    ) -> list[Trendbar]:
        info = await self._get_symbol(int(account_id), symbol.upper())
        req = ProtoOAGetTrendbarsReq(
            ctidTraderAccountId=int(account_id),
            symbolId=info.symbol_id,
            period=ProtoOATrendbarPeriod.Value(timeframe.value),
            fromTimestamp=from_ts,
        )
        if to_ts:
            req.toTimestamp = to_ts
        if limit:
            req.count = limit
        res = await self._send_request(req)

        if isinstance(res, ProtoOAErrorRes):
            error_res = cast(ProtoOAErrorRes, res)
            raise RuntimeError(
                f"cTrader API error (code {error_res.errorCode}): {error_res.description}"
            )

        res = cast(ProtoOAGetTrendbarsRes, res)

        return [
            map_trendbar(tb, digits=info.digits)
            for tb in res.trendbar
        ]

    async def list_symbols(
        self,
        account_id: AccountId,
    ) -> list[SymbolDescriptor]:
        await self._symbol_cache.ensure_populated(
            int(account_id),
            self._authorize_account,
            self._send_request,
        )

        return self._symbol_cache.get_all_descriptors()

    async def get_symbol(self, account_id: AccountId, symbol: str) -> Symbol:
        symbol_data = await self._get_symbol(int(account_id), symbol.upper())
        return symbol_data

    # ---------------------------------------------------------- tick streaming

    async def register_tick_handler(
        self,
        account_id: int,
        symbol: str,
        handler: TickHandler,
    ) -> TickSubscription:
        full_info = await self._get_symbol(account_id, symbol.upper())

        key = (account_id, full_info.symbol_id)
        token = str(uuid.uuid4())
        async with self._tick_lock:
            handlers = self._tick_handlers.setdefault(key, {})
            handlers[token] = handler

            if key not in self._active_tick_streams:
                await self._subscribe_spots(account_id, full_info.symbol_id)
                self._active_tick_streams.add(key)

        return TickSubscription(
            account_id=account_id,
            symbol=full_info.symbol_name,
            symbol_id=full_info.symbol_id,
            token=token,
        )

    async def unregister_tick_handler(
        self,
        subscription: TickSubscription
    ) -> None:
        """Unregister a tick handler."""
        key = (subscription.account_id, subscription.symbol_id)
        async with self._tick_lock:
            handlers = self._tick_handlers.get(key)
            if not handlers:
                return

            handlers.pop(subscription.token, None)

            if not handlers:
                self._tick_handlers.pop(key, None)

                if key in self._active_tick_streams:
                    await self._unsubscribe_spots(
                        subscription.account_id,
                        subscription.symbol_id
                    )

                    self._active_tick_streams.remove(key)

    # ------------------------------------------------------ trendbar streaming

    async def register_trendbar_handler(
        self,
        account_id: int,
        symbol: str,
        timeframe: Timeframe,
        handler: TrendbarHandler,
    ) -> TrendbarSubscription:
        full_info = await self._get_symbol(account_id, symbol.upper())

        key = (account_id, full_info.symbol_id, timeframe.value)
        token = str(uuid.uuid4())

        async with self._trendbar_lock:
            handlers = self._trendbar_handlers.setdefault(key, {})
            handlers[token] = handler

            if key not in self._active_trendbar_streams:
                spot_key = (account_id, full_info.symbol_id)
                async with self._tick_lock:
                    if spot_key not in self._active_tick_streams:
                        await self._subscribe_spots(
                            account_id,
                            full_info.symbol_id
                        )
                        self._active_tick_streams.add(spot_key)

                await self._subscribe_live_trendbar(
                    account_id,
                    full_info.symbol_id,
                    timeframe
                )
                self._active_trendbar_streams.add(key)

        return TrendbarSubscription(
            account_id=account_id,
            symbol=full_info.symbol_name,
            symbol_id=full_info.symbol_id,
            timeframe=timeframe,
            token=token,
        )

    async def unregister_trendbar_handler(
        self,
        subscription: "TrendbarSubscription"
    ) -> None:
        key = (subscription.account_id, subscription.symbol_id,
               subscription.timeframe.value)

        async with self._trendbar_lock:
            handlers = self._trendbar_handlers.get(key)
            if not handlers:
                return

            handlers.pop(subscription.token, None)
            if not handlers:
                self._trendbar_handlers.pop(key, None)
                if key in self._active_trendbar_streams:
                    await self._unsubscribe_live_trendbar(
                        subscription.account_id,
                        subscription.symbol_id,
                        subscription.timeframe,
                    )
                    self._active_trendbar_streams.remove(key)

    # --------------------------------------------------------------- internals

    def _start_reactor(self) -> None:
        try:
            self._client.startService()
            reactor.run(installSignalHandlers=0)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.exception(
                "Twisted reactor crashed while running cTrader client service "
                "(shutting_down=%s, thread=%s, reactor_running=%s)",
                getattr(self, "_shutting_down", None),
                threading.current_thread().name,
                getattr(reactor, "running", None),
            )

    def _on_connected(self, client: Client) -> None:
        req = ProtoOAApplicationAuthReq(
            clientId=self._credentials.client_id,
            clientSecret=self._credentials.secret,
        )
        deferred = client.send(req)
        deferred.addErrback(
            lambda failure: logger.error("App auth error: %s", failure)
        )

    def _on_disconnected(self, client: Client, reason: str) -> None:
        if self._shutting_down:
            logger.info("Disconnected from cTrader (graceful shutdown)")
        else:
            logger.warning("Disconnected from cTrader: %s", reason)
        self._app_authenticated.clear()
        self._authorized_accounts.clear()

    def _on_message(self, client: Client, message) -> None:
        if self._loop is None:
            return

        payload_type = message.payloadType
        if payload_type == ProtoOAApplicationAuthRes().payloadType:
            self._loop.call_soon_threadsafe(self._app_authenticated.set)
            return

        if payload_type == ProtoOAAccountAuthRes().payloadType:
            proto = cast(ProtoOAAccountAuthRes, Protobuf.extract(message))
            self._authorized_accounts.add(proto.ctidTraderAccountId)
            return

        if payload_type == ProtoOASpotEvent().payloadType:
            event = cast(ProtoOASpotEvent, Protobuf.extract(message))
            asyncio.run_coroutine_threadsafe(
                self._emit_tick(event), self._loop)

            if event.trendbar:
                asyncio.run_coroutine_threadsafe(
                    self._emit_trendbars(event), self._loop)
            return

    async def _emit_tick(self, event: ProtoOASpotEvent) -> None:
        """Emit tick events to registered handlers."""
        key = (event.ctidTraderAccountId, event.symbolId)
        async with self._tick_lock:
            handlers = list(self._tick_handlers.get(key, {}).values())
        if not handlers:
            return

        info = self._symbol_cache.get_full_by_id(event.symbolId)
        if not info:
            logger.warning("No symbol info for symbol_id=%s", event.symbolId)
            return

        tick = map_tick(event.bid, event.ask, event.timestamp, info.digits)
        await asyncio.gather(
            *(handler(tick) for handler in handlers),
            return_exceptions=True
        )

    async def _emit_trendbars(self, event: ProtoOASpotEvent) -> None:
        """Emit live trendbars from a spot event to registered handlers."""
        info = self._symbol_cache.get_full_by_id(event.symbolId)
        if not info:
            logger.warning(
                "No symbol info for trendbar symbol_id=%s", event.symbolId)
            return

        # Get the bid price from the spot event as close price for live bars.
        bid_price: int | None = event.bid if event.bid else None

        for proto_bar in event.trendbar:
            try:
                timeframe = resolve_timeframe(proto_bar.period)
            except ValueError:
                logger.warning("Unknown trendbar period: %s", proto_bar.period)
                continue

            key = (event.ctidTraderAccountId, event.symbolId, timeframe.value)
            async with self._trendbar_lock:
                handlers = list(self._trendbar_handlers.get(key, {}).values())

            if not handlers:
                continue

            trendbar = map_trendbar(
                proto_bar,
                bid_price=bid_price,
                digits=info.digits
            )
            await asyncio.gather(
                *(handler(trendbar) for handler in handlers),
                return_exceptions=True,
            )

    async def _subscribe_spots(self, account_id: int, symbol_id: int) -> None:
        req = ProtoOASubscribeSpotsReq(ctidTraderAccountId=account_id)
        req.symbolId.append(symbol_id)
        await self._send_request(req)

    async def _unsubscribe_spots(
        self,
        account_id: int,
        symbol_id: int,
    ) -> None:
        req = ProtoOAUnsubscribeSpotsReq(ctidTraderAccountId=account_id)
        req.symbolId.append(symbol_id)
        await self._send_request(req)

    async def _subscribe_live_trendbar(
        self, account_id: int, symbol_id: int, timeframe: Timeframe
    ) -> None:
        """Subscribe to live trendbars for a symbol and timeframe."""
        req = ProtoOASubscribeLiveTrendbarReq(
            ctidTraderAccountId=account_id,
            symbolId=symbol_id,
            period=ProtoOATrendbarPeriod.Value(timeframe.value),
        )
        await self._send_request(req)

    async def _unsubscribe_live_trendbar(
        self,
        account_id: int,
        symbol_id: int,
        timeframe: Timeframe,
    ) -> None:
        """Unsubscribe from live trendbars for a symbol and timeframe."""
        req = ProtoOAUnsubscribeLiveTrendbarReq(
            ctidTraderAccountId=account_id,
            symbolId=symbol_id,
            period=ProtoOATrendbarPeriod.Value(timeframe.value),
        )
        await self._send_request(req)

    async def _send_request(
        self,
        message: Message,
        timeout: float | None = None
    ) -> Message:
        await self._app_authenticated.wait()
        effective_timeout = (
            timeout if timeout and timeout > 0
            else self._request_timeout
        )
        timeout_seconds = int(effective_timeout)
        if timeout_seconds <= 0:
            timeout_seconds = 1

        deferred = self._client.send(
            message,
            responseTimeoutInSeconds=timeout_seconds
        )
        response = await self._await_deferred(deferred)

        return cast(Message, Protobuf.extract(response))

    async def _await_deferred(self, deferred: Deferred) -> Message:
        if not self._loop:
            raise RuntimeError("Client loop not initialized")

        loop = self._loop
        future: asyncio.Future[Message] = loop.create_future()

        def _ok(result):
            loop.call_soon_threadsafe(future.set_result, result)

        def _err(failure):
            loop.call_soon_threadsafe(
                future.set_exception,
                failure.value if failure else RuntimeError(
                    "cTrader request failed"),
            )

        deferred.addCallbacks(_ok, _err)

        return await future

    async def _authorize_account(self, account_id: int) -> None:
        if account_id in self._authorized_accounts:
            return

        req = ProtoOAAccountAuthReq(
            ctidTraderAccountId=account_id,
            accessToken=self._credentials.access_token,
        )
        await self._send_request(req)
        self._authorized_accounts.add(account_id)

    async def _get_trader(self, account_id: int):
        await self._authorize_account(account_id)

        req = ProtoOATraderReq(ctidTraderAccountId=account_id)
        res = await self._send_request(req)

        if isinstance(res, ProtoOAErrorRes):
            error_res = cast(ProtoOAErrorRes, res)
            raise RuntimeError(
                f"cTrader API error (code {error_res.errorCode}): {error_res.description}"
            )

        res = cast(ProtoOATraderRes, res)

        return res.trader

    async def _reconcile(self, account_id: AccountId):
        await self._authorize_account(int(account_id))

        req = ProtoOAReconcileReq(ctidTraderAccountId=int(account_id))
        res = await self._send_request(req)

        if isinstance(res, ProtoOAErrorRes):
            error_res = cast(ProtoOAErrorRes, res)
            raise RuntimeError(
                f"cTrader API error (code {error_res.errorCode}): {error_res.description}"
            )

        res = cast(ProtoOAReconcileRes, res)

        return res

    async def _get_light_symbol(
        self,
        account_id: int,
        name: str,
    ) -> SymbolDescriptor:
        """Get basic symbol info (name, id, enabled)."""
        return await self._symbol_cache.get_light_symbol(
            account_id,
            name,
            self._authorize_account,
            self._send_request,
        )

    async def _get_symbol(self, account_id: int, name: str) -> Symbol:
        """Get full symbol info (with digits, pip position, etc.)."""
        return await self._symbol_cache.get_or_fetch_symbol(
            account_id,
            name,
            self._authorize_account,
            self._send_request,
        )
