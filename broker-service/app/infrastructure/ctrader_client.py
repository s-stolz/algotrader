import asyncio
import logging
import threading
import time
import uuid
from dataclasses import replace
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Mapping, Tuple, cast

from app.application.interfaces import BrokerPort, MarketDataPort
from app.domain.models import Account, Deal, Order, Position, Symbol, Tick, Trendbar
from app.domain.value_objects import (
    AccountId,
    OrderId,
    PositionId,
    SymbolDescriptor,
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
from app.infrastructure.ctrader_protocol import CtraderProtocol
from app.infrastructure.ctrader_symbol_cache import SymbolCache
from app.infrastructure.stream_registry import (
    TickSubscription,
    TrendbarSubscription,
)
from app.settings import CtraderCredentials
from ctrader_open_api import Client, Protobuf
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
    ProtoOAOrderType,
    ProtoOATimeInForce,
    ProtoOATradeSide,
    ProtoOATrendbarPeriod,
)
from google.protobuf.message import Message
from twisted.internet import reactor
from twisted.internet.defer import Deferred

logger = logging.getLogger(__name__)

TickHandler = Callable[[Tick], Awaitable[None]]
TrendbarHandler = Callable[[Trendbar], Awaitable[None]]

TRENDBAR_FETCH_CONCURRENCY = 2
TRENDBAR_RATE_LIMIT_RETRIES = 3
TRENDBAR_RETRY_BASE_DELAY_SECONDS = 0.25


def _timeframe_to_minutes(timeframe: Timeframe) -> int:
    """Convert timeframe to minutes for chunk size calculation."""
    mapping = {
        Timeframe.M1: 1,
        Timeframe.M2: 2,
        Timeframe.M3: 3,
        Timeframe.M4: 4,
        Timeframe.M5: 5,
        Timeframe.M10: 10,
        Timeframe.M15: 15,
        Timeframe.M30: 30,
        Timeframe.H1: 60,
        Timeframe.H4: 240,
        Timeframe.H12: 720,
        Timeframe.D1: 1440,
        Timeframe.W1: 10080,
        Timeframe.MN1: 43200,  # Approximate
    }
    return mapping.get(timeframe, 1)


def _trendbar_count_for_range(
    timeframe: Timeframe,
    from_ts: int,
    to_ts: int | None,
    max_count: int,
) -> int:
    if to_ts is None:
        return max_count

    if to_ts < from_ts:
        return 0

    timeframe_ms = _timeframe_to_minutes(timeframe) * 60 * 1000
    range_count = ((to_ts - from_ts) // timeframe_ms) + 1
    return min(max_count, range_count)


def _trendbar_chunk_to(
    timeframe: Timeframe,
    from_ts: int,
    chunk_size: int,
    final_to: int | None,
) -> int:
    timeframe_ms = _timeframe_to_minutes(timeframe) * 60 * 1000
    chunk_to = from_ts + ((chunk_size - 1) * timeframe_ms)
    return min(chunk_to, final_to) if final_to is not None else chunk_to


def _filter_trendbars_by_time_range(
    bars: list[Trendbar],
    from_ts: int,
    to_ts: int | None,
) -> list[Trendbar]:
    if to_ts is None:
        return [bar for bar in bars if bar.t >= from_ts]

    return [bar for bar in bars if from_ts <= bar.t <= to_ts]


class CtraderClient(BrokerPort, MarketDataPort):
    """Async wrapper that keeps Twisted reactor in a background thread."""

    def __init__(
        self,
        credentials: CtraderCredentials,
        request_timeout: float = 5.0,
        access_token_provider: Callable[[], str] | None = None,
    ) -> None:
        self._credentials = credentials
        self._request_timeout = max(1.0, float(request_timeout))
        self._access_token_provider = access_token_provider or (
            lambda: self._credentials.access_token
        )

        # Twisted client setup
        self._client = self._create_client(credentials)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._reactor_thread: threading.Thread | None = None

        # Authentication state
        self._app_authenticated = asyncio.Event()
        self._authorized_accounts: set[int] = set()

        # Shutdown state
        self._continuity = "v1:" + uuid.uuid4().hex
        self._shutting_down = False
        self._subscription_restore_task: asyncio.Task[None] | None = None
        self._application_auth_task: asyncio.Task[None] | None = None

        # Symbol cache
        self._symbol_cache = SymbolCache()

        # Tick streaming state
        self._tick_handlers: Dict[Tuple[int, int], Dict[str, TickHandler]] = {}
        self._tick_lock = asyncio.Lock()
        self._active_tick_streams: set[Tuple[int, int]] = set()

        # Trendbar streaming state (key: account_id, symbol_id, timeframe)
        self._trendbar_handlers: Dict[Tuple[int, int, str], Dict[str, TrendbarHandler]] = {}
        self._trendbar_lock = asyncio.Lock()
        self._active_trendbar_streams: set[Tuple[int, int, str]] = set()

        # Limit concurrent historical trendbar requests to reduce cTrader rate-limit bursts.
        self._trendbar_fetch_semaphore = asyncio.Semaphore(TRENDBAR_FETCH_CONCURRENCY)

    def _create_client(self, credentials: CtraderCredentials) -> Client:
        """Create and configure the Twisted client."""
        endpoint = (
            EndPoints.PROTOBUF_LIVE_HOST
            if credentials.host_type.lower() == "live"
            else EndPoints.PROTOBUF_DEMO_HOST
        )
        client = Client(endpoint, EndPoints.PROTOBUF_PORT, CtraderProtocol)
        client.setConnectedCallback(self._on_connected)
        client.setDisconnectedCallback(self._on_disconnected)
        client.setMessageReceivedCallback(self._on_message)
        return client

    # ------------------------------------------------------------- lifecycle

    async def connect(self) -> None:
        if self._reactor_thread:
            return
        self._loop = asyncio.get_running_loop()
        self._reactor_thread = threading.Thread(target=self._start_reactor, daemon=True)
        self._reactor_thread.start()
        await self._app_authenticated.wait()

    async def disconnect(self) -> None:
        self._shutting_down = True
        if self._application_auth_task is not None:
            self._application_auth_task.cancel()
            await asyncio.gather(self._application_auth_task, return_exceptions=True)
        if self._subscription_restore_task is not None:
            self._subscription_restore_task.cancel()
            await asyncio.gather(self._subscription_restore_task, return_exceptions=True)
        for account_id in list(self._authorized_accounts):
            try:
                await self._send_request(ProtoOAAccountLogoutReq(ctidTraderAccountId=account_id))
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

    async def reset_authorized_accounts(self) -> None:
        self._authorized_accounts.clear()

    # ------------------------------------------------------------- BrokerPort

    async def list_accounts(self) -> list[Account]:
        res = cast(
            ProtoOAGetAccountListByAccessTokenRes,
            await self._send_request(
                ProtoOAGetAccountListByAccessTokenReq(accessToken=self._access_token_provider())
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
        return [map_order(order, self._symbol_cache.get_by_id) for order in data.order]

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
        return [map_order(order, self._symbol_cache.get_by_id) for order in res.order]

    async def place_order(
        self,
        account_id: AccountId,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        symbol = payload["symbol"].upper()
        account_id_int = int(account_id)
        info = await self._get_symbol(account_id_int, symbol)
        req = ProtoOANewOrderReq(ctidTraderAccountId=account_id_int)
        req.symbolId = info.symbol_id
        req.orderType = ProtoOAOrderType.Value(payload["orderType"])
        req.tradeSide = ProtoOATradeSide.Value(payload["tradeSide"])
        req.volume = payload["volume"]
        if "limitPrice" in payload:
            req.limitPrice = payload["limitPrice"]
        if "stopPrice" in payload:
            req.stopPrice = payload["stopPrice"]
        if "stopLoss" in payload:
            req.stopLoss = payload["stopLoss"]
        if "takeProfit" in payload:
            req.takeProfit = payload["takeProfit"]
        if "timeInForce" in payload:
            req.timeInForce = ProtoOATimeInForce.Value(payload["timeInForce"])
        if "expirationTimestamp" in payload:
            req.expirationTimestamp = payload["expirationTimestamp"]
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

    async def cancel_order(self, account_id: AccountId, order_id: OrderId) -> None:
        req = ProtoOACancelOrderReq(
            ctidTraderAccountId=int(account_id),
            orderId=int(order_id),
        )
        await self._send_request(req)

    async def get_open_positions(self, account_id: AccountId) -> list[Position]:
        data = await self._reconcile(account_id)
        return [map_position(pos, self._symbol_cache.get_by_id) for pos in data.position]

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
        return [map_deal(deal, self._symbol_cache.get_by_id) for deal in res.deal]

    async def close_position(
        self,
        account_id: AccountId,
        position_id: PositionId,
        close_volume: int | None = None,
    ) -> dict[str, Any]:
        req = ProtoOAClosePositionReq(
            ctidTraderAccountId=int(account_id), positionId=int(position_id)
        )
        if close_volume:
            req.volume = int(close_volume)
        await self._send_request(req)

        return {
            "status": "close-requested",
            "positionId": int(position_id),
        }

    # ---------------------------------------------------------- MarketDataPort

    async def get_trendbars(  # noqa: C901
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        from_ts: int,
        to_ts: int | None,
        limit: int | None,
    ) -> list[Trendbar]:
        """Fetch finite history, retaining newest-first selection for limited queries."""
        if limit is not None:
            info = await self._get_symbol(int(account_id), symbol.upper())
            page_to = to_ts if to_ts is not None else int(time.time() * 1000)
            bars: list[Trendbar] = []
            while from_ts <= page_to and len(bars) < limit:
                page = await self._fetch_trendbar_chunk(
                    int(account_id),
                    info.symbol_id,
                    info.digits,
                    timeframe,
                    from_ts,
                    page_to,
                    min(10000, limit - len(bars)),
                )
                if not page:
                    break
                timestamps = [bar.t for bar in page]
                if len(set(timestamps)) != len(timestamps) or max(timestamps) > page_to:
                    raise RuntimeError(
                        "cTrader historical pagination did not advance within interval"
                    )
                # Count-based provider pages can extend before fromTimestamp.
                bars.extend(bar for bar in page if bar.t >= from_ts)
                page_to = min(timestamps) - 1
            return sorted(bars, key=lambda item: item.t)[-limit:]
        return [
            bar
            async for bar in self.stream_trendbars(
                account_id, symbol, timeframe, from_ts, to_ts, limit
            )
        ]

    async def _fetch_trendbar_chunk(
        self,
        account_id: int,
        symbol_id: int,
        digits: int,
        timeframe: Timeframe,
        from_ts: int,
        to_ts: int | None,
        limit: int | None,
    ) -> list[Trendbar]:
        """Fetch a single chunk of trendbars from the cTrader API."""
        attempt = 0
        while True:
            attempt += 1
            async with self._trendbar_fetch_semaphore:
                req = ProtoOAGetTrendbarsReq(
                    ctidTraderAccountId=account_id,
                    symbolId=symbol_id,
                    period=ProtoOATrendbarPeriod.Value(timeframe.value),
                    fromTimestamp=from_ts,
                )
                if to_ts is not None:
                    req.toTimestamp = to_ts
                if limit:
                    req.count = limit

                res = await self._send_request(req)

            if isinstance(res, ProtoOAGetTrendbarsRes):
                res = cast(ProtoOAGetTrendbarsRes, res)
                if not res.IsInitialized():
                    raise RuntimeError("Incomplete cTrader historical response")
                if not res.trendbar and getattr(res, "hasMore", False):
                    raise RuntimeError("cTrader reports more history without a pagination cursor")
                return [map_trendbar(tb, digits=digits) for tb in res.trendbar]
            if not isinstance(res, ProtoOAErrorRes):
                raise RuntimeError("Unexpected cTrader historical response")

            error_res = cast(ProtoOAErrorRes, res)
            if not self._is_rate_limit_error(error_res.description):
                raise RuntimeError(
                    f"cTrader API error (code {error_res.errorCode}): {error_res.description}"
                )

            if attempt > TRENDBAR_RATE_LIMIT_RETRIES:
                raise RuntimeError(
                    "cTrader API rate limit exceeded for trendbar requests after retries: "
                    f"{error_res.description}"
                )

            delay_seconds = TRENDBAR_RETRY_BASE_DELAY_SECONDS * attempt
            logger.warning(
                "Rate limited while fetching trendbars "
                "(attempt=%s/%s, delay=%.2fs, symbol_id=%s, timeframe=%s)",
                attempt,
                TRENDBAR_RATE_LIMIT_RETRIES,
                delay_seconds,
                symbol_id,
                timeframe.value,
            )
            await asyncio.sleep(delay_seconds)

    async def stream_trendbars(  # noqa: C901
        self,
        account_id: AccountId,
        symbol: str,
        timeframe: Timeframe,
        from_ts: int,
        to_ts: int | None,
        limit: int | None,
    ) -> AsyncIterator[Trendbar]:
        """Exhaust finite windows, paging backwards as cTrader's count requires."""
        info = await self._get_symbol(int(account_id), symbol.upper())
        final_to = to_ts if to_ts is not None else int(time.time() * 1000)
        window_span = 10000 * _timeframe_to_minutes(timeframe) * 60 * 1000
        current_from = from_ts
        total_yielded = 0

        while current_from <= final_to:
            window_to = min(current_from + window_span - 1, final_to)
            page_to = window_to
            window_bars: list[Trendbar] = []
            while page_to >= current_from:
                page = await self._fetch_trendbar_chunk(
                    int(account_id),
                    info.symbol_id,
                    info.digits,
                    timeframe,
                    current_from,
                    page_to,
                    10000,
                )
                if not page:
                    break
                timestamps = [bar.t for bar in page]
                if len(set(timestamps)) != len(timestamps) or max(timestamps) > page_to:
                    raise RuntimeError(
                        "cTrader historical pagination did not advance within interval"
                    )
                # Keep only this window; older count-based bars prove its lower bound.
                window_bars.extend(bar for bar in page if bar.t >= current_from)
                # Even a short page can be provider-limited. Query the earlier remainder.
                page_to = min(timestamps) - 1

            for bar in sorted(window_bars, key=lambda item: item.t):
                yield bar
                total_yielded += 1
                if limit is not None and total_yielded >= limit:
                    return
            current_from = window_to + 1

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

    async def unregister_tick_handler(self, subscription: TickSubscription) -> None:
        """Unregister a tick handler."""
        key = (subscription.account_id, subscription.symbol_id)
        async with self._trendbar_lock, self._tick_lock:
            handlers = self._tick_handlers.get(key)
            if not handlers:
                return

            handlers.pop(subscription.token, None)

            if not handlers:
                self._tick_handlers.pop(key, None)

                if key in self._active_tick_streams:
                    has_trendbar_subscriptions = False
                    for acc_id, sym_id, _ in self._trendbar_handlers.keys():
                        if acc_id == subscription.account_id and sym_id == subscription.symbol_id:
                            has_trendbar_subscriptions = True
                            break

                    if not has_trendbar_subscriptions:
                        await self._unsubscribe_spots(
                            subscription.account_id, subscription.symbol_id
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

            try:
                if key not in self._active_trendbar_streams:
                    spot_key = (account_id, full_info.symbol_id)
                    async with self._tick_lock:
                        if spot_key not in self._active_tick_streams:
                            await self._subscribe_spots(account_id, full_info.symbol_id)
                            self._active_tick_streams.add(spot_key)

                    await self._subscribe_live_trendbar(account_id, full_info.symbol_id, timeframe)
                    self._active_trendbar_streams.add(key)
            except BaseException:
                handlers.pop(token, None)
                if not handlers:
                    self._trendbar_handlers.pop(key, None)
                raise

        return TrendbarSubscription(
            account_id=account_id,
            symbol=full_info.symbol_name,
            symbol_id=full_info.symbol_id,
            timeframe=timeframe,
            token=token,
        )

    async def unregister_trendbar_handler(self, subscription: "TrendbarSubscription") -> None:
        key = (subscription.account_id, subscription.symbol_id, subscription.timeframe.value)

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
        except Exception:
            logger.exception(
                "Twisted reactor crashed while running cTrader client service "
                "(shutting_down=%s, thread=%s, reactor_running=%s)",
                getattr(self, "_shutting_down", None),
                threading.current_thread().name,
                getattr(reactor, "running", None),
            )

    def _on_connected(self, client: Client) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._start_application_authentication)

    def _start_application_authentication(self) -> None:
        if self._shutting_down:
            return
        if self._application_auth_task is not None:
            self._application_auth_task.cancel()
        self._application_auth_task = asyncio.create_task(self._authenticate_application())

    async def _authenticate_application(self) -> None:
        delay = 1
        while not self._shutting_down:
            try:
                req = ProtoOAApplicationAuthReq(
                    clientId=self._credentials.client_id,
                    clientSecret=self._credentials.secret,
                )
                response = await self._await_deferred(self._client.send(req))
                if not isinstance(Protobuf.extract(response), ProtoOAApplicationAuthRes):
                    raise RuntimeError("cTrader application authorization failed")
                return
            except Exception:
                logger.exception("Failed cTrader application authentication; retry=%s", delay)
                await asyncio.sleep(delay)
                delay = min(30, delay * 2)

    def _on_disconnected(self, client: Client, reason: str) -> None:
        # Twisted serializes transport callbacks. Capture identity there, before
        # dispatching event coroutines, so queued old events cannot inherit it.
        self._continuity = "v1:" + uuid.uuid4().hex
        if self._shutting_down:
            logger.info("Disconnected from cTrader (graceful shutdown)")
        else:
            logger.warning("Disconnected from cTrader: %s", reason)
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._connection_lost)

    def _connection_lost(self) -> None:
        self._app_authenticated.clear()
        if self._application_auth_task is not None:
            self._application_auth_task.cancel()
        self._authorized_accounts.clear()
        self._active_tick_streams.clear()
        self._active_trendbar_streams.clear()
        if self._subscription_restore_task is not None:
            self._subscription_restore_task.cancel()

    def _application_authenticated(self) -> None:
        self._app_authenticated.set()
        if self._shutting_down:
            return
        if self._subscription_restore_task is not None:
            self._subscription_restore_task.cancel()
        self._subscription_restore_task = asyncio.create_task(self._restore_subscriptions())

    async def _restore_subscriptions(self) -> None:
        delay = 1
        while not self._shutting_down and self.is_connected:
            unfinished = False
            # Registration and restoration share one lock order. Retain handlers
            # but acknowledge active subscriptions only after upstream success.
            async with self._trendbar_lock, self._tick_lock:
                spot_keys = set(self._tick_handlers) | {
                    (account_id, symbol_id) for account_id, symbol_id, _ in self._trendbar_handlers
                }
                for account_id, symbol_id in sorted(spot_keys):
                    if (account_id, symbol_id) not in self._active_tick_streams:
                        try:
                            await self._authorize_account(account_id)
                            await self._subscribe_spots(account_id, symbol_id)
                            self._active_tick_streams.add((account_id, symbol_id))
                        except Exception:
                            unfinished = True
                            logger.exception(
                                "Failed to restore cTrader spots; account=%s symbol_id=%s retry=%s",
                                account_id,
                                symbol_id,
                                delay,
                            )
                for key in list(self._trendbar_handlers):
                    if key not in self._active_trendbar_streams:
                        account_id, symbol_id, timeframe = key
                        # A failed spot subscription blocks only its own trendbars.
                        if (account_id, symbol_id) not in self._active_tick_streams:
                            continue
                        try:
                            await self._subscribe_live_trendbar(
                                account_id, symbol_id, Timeframe(timeframe)
                            )
                            self._active_trendbar_streams.add(key)
                        except Exception:
                            unfinished = True
                            logger.exception(
                                "Failed to restore cTrader trendbars; account=%s symbol_id=%s "
                                "timeframe=%s retry=%s",
                                account_id,
                                symbol_id,
                                timeframe,
                                delay,
                            )
            if not unfinished:
                return
            await asyncio.sleep(delay)
            delay = min(30, delay * 2)

    def _on_message(self, client: Client, message) -> None:
        if self._loop is None:
            return

        payload_type = message.payloadType
        if payload_type == ProtoOAApplicationAuthRes().payloadType:
            self._loop.call_soon_threadsafe(self._application_authenticated)
            return

        if payload_type == ProtoOAAccountAuthRes().payloadType:
            proto = cast(ProtoOAAccountAuthRes, Protobuf.extract(message))
            self._authorized_accounts.add(proto.ctidTraderAccountId)
            return

        if payload_type == ProtoOASpotEvent().payloadType:
            event = cast(ProtoOASpotEvent, Protobuf.extract(message))
            asyncio.run_coroutine_threadsafe(self._emit_tick(event), self._loop)

            if event.trendbar:
                asyncio.run_coroutine_threadsafe(
                    self._emit_trendbars(event, self._continuity), self._loop
                )
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
        if len(handlers) == 1:
            try:
                await handlers[0](tick)
            except Exception:
                logger.exception("Tick handler failed for account=%s symbol_id=%s", *key)
            return

        await asyncio.gather(*(handler(tick) for handler in handlers), return_exceptions=True)

    async def _emit_trendbars(self, event: ProtoOASpotEvent, continuity: str | None = None) -> None:
        """Emit live trendbars from a spot event to registered handlers."""
        continuity = continuity or self._continuity
        if continuity != self._continuity:
            return
        info = self._symbol_cache.get_full_by_id(event.symbolId)
        if not info:
            logger.warning("No symbol info for trendbar symbol_id=%s", event.symbolId)
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

            if continuity != self._continuity:
                return
            if not handlers:
                continue

            trendbar = map_trendbar(proto_bar, bid_price=bid_price, digits=info.digits)
            trendbar = replace(trendbar, continuity=continuity)
            if len(handlers) == 1:
                try:
                    await handlers[0](trendbar)
                except Exception:
                    logger.exception(
                        "Trendbar handler failed for account=%s symbol_id=%s timeframe=%s",
                        event.ctidTraderAccountId,
                        event.symbolId,
                        timeframe.value,
                    )
                continue

            await asyncio.gather(
                *(handler(trendbar) for handler in handlers),
                return_exceptions=True,
            )

    async def _subscribe_spots(self, account_id: int, symbol_id: int) -> None:
        req = ProtoOASubscribeSpotsReq(ctidTraderAccountId=account_id)
        req.symbolId.append(symbol_id)
        response = await self._send_request(req)
        if isinstance(response, ProtoOAErrorRes):
            error_res = cast(ProtoOAErrorRes, response)
            raise RuntimeError(
                f"cTrader subscription failed: {error_res.errorCode}: {error_res.description}"
            )

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
        response = await self._send_request(req)
        if isinstance(response, ProtoOAErrorRes):
            error_res = cast(ProtoOAErrorRes, response)
            raise RuntimeError(
                f"cTrader subscription failed: {error_res.errorCode}: {error_res.description}"
            )

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

    async def _send_request(self, message: Message, timeout: float | None = None) -> Message:
        await self._app_authenticated.wait()
        effective_timeout = timeout if timeout and timeout > 0 else self._request_timeout
        timeout_seconds = int(effective_timeout)
        if timeout_seconds <= 0:
            timeout_seconds = 1

        continuity = self._continuity
        deferred = self._client.send(message, responseTimeoutInSeconds=timeout_seconds)
        response = await self._await_deferred(deferred)
        if continuity != self._continuity:
            raise RuntimeError("cTrader connection changed during request")

        return cast(Message, Protobuf.extract(response))

    async def _await_deferred(self, deferred: Deferred) -> Message:
        if not self._loop:
            raise RuntimeError("Client loop not initialized")

        loop = self._loop
        future: asyncio.Future[Message] = loop.create_future()

        def _resolve(result):
            if not future.done():
                future.set_result(result)

        def _reject(error):
            if not future.done():
                future.set_exception(error)

        def _ok(result):
            loop.call_soon_threadsafe(_resolve, result)

        def _err(failure):
            loop.call_soon_threadsafe(
                _reject,
                failure.value if failure else RuntimeError("cTrader request failed"),
            )

        deferred.addCallbacks(_ok, _err)

        return await future

    async def _authorize_account(self, account_id: int) -> None:
        if account_id in self._authorized_accounts:
            return

        req = ProtoOAAccountAuthReq(
            ctidTraderAccountId=account_id,
            accessToken=self._access_token_provider(),
        )
        res = await self._send_request(req)
        if isinstance(res, ProtoOAErrorRes):
            raise RuntimeError(
                f"cTrader account authorization failed (code {res.errorCode}): {res.description}"
            )
        if not isinstance(res, ProtoOAAccountAuthRes) or res.ctidTraderAccountId != account_id:
            raise RuntimeError("Unexpected cTrader account authorization response")
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

    @staticmethod
    def _is_rate_limit_error(description: str | None) -> bool:
        if not description:
            return False
        lowered = description.lower()
        return "request_frequency_exceeded" in lowered or "rate limit" in lowered
