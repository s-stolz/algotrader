"""Deliver download invalidations; durable job snapshots remain in ingestion."""

import asyncio
import json
import logging
from typing import cast

from redis.asyncio import Redis
from websockets.asyncio.server import ServerConnection

_LOGGER = logging.getLogger(__name__)
_STREAM = "history:downloads:events"


class HistoryDownloadEventBridge:
    def __init__(self, redis: Redis):
        self._redis = redis
        self._clients: dict[ServerConnection, set[int]] = {}
        self._connected = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def subscribe(self, websocket: ServerConnection, market_id: int) -> None:
        self._clients.setdefault(websocket, set()).add(market_id)
        await self._send(websocket, self._connection_message(market_id))

    def unsubscribe(self, websocket: ServerConnection, market_id: int | None = None) -> None:
        if market_id is None:
            self._clients.pop(websocket, None)
            return
        markets = self._clients.get(websocket)
        if markets is not None:
            markets.discard(market_id)
            if not markets:
                self._clients.pop(websocket, None)

    def _connection_message(self, market_id: int) -> dict:
        return {
            "type": "historyDownloadsConnection",
            "market_id": market_id,
            "connected": self._connected,
        }

    async def _send(self, websocket: ServerConnection, message: dict) -> None:
        try:
            await asyncio.wait_for(websocket.send(json.dumps(message)), timeout=5)
        except Exception:
            self._clients.pop(websocket, None)
            try:
                await websocket.close()
            except Exception:
                _LOGGER.debug("Download subscriber already closed", exc_info=True)

    async def _connection(self, connected: bool) -> None:
        self._connected = connected
        await asyncio.gather(
            *(
                self._send(websocket, self._connection_message(market_id))
                for websocket, markets in list(self._clients.items())
                for market_id in list(markets)
            )
        )

    async def _broadcast(self, message: dict) -> None:
        await asyncio.gather(
            *(
                self._send(websocket, message)
                for websocket, markets in list(self._clients.items())
                if message["market_id"] in markets
            )
        )

    @staticmethod
    def _read_event(fields: dict[str, str]) -> dict | None:
        try:
            event = json.loads(fields["event"])
        except (KeyError, TypeError, ValueError):
            return None
        if event == {"type": "historyDownloadsResnapshot"}:
            return event
        if (
            not isinstance(event, dict)
            or event.get("type") != "historyDownloadChanged"
            or type(event.get("market_id")) is not int
            or event["market_id"] <= 0
            or not isinstance(event.get("job_id"), str)
            or not event["job_id"]
            or type(event.get("revision")) is not int
            or event["revision"] < 0
        ):
            return None
        return {key: event[key] for key in ("type", "market_id", "job_id", "revision")}

    async def _run(self) -> None:
        while True:
            try:
                tail = cast(
                    list[tuple[str, dict[str, str]]], await self._redis.xrevrange(_STREAM, count=1)
                )
                cursor = tail[0][0] if tail else "0-0"
                # A concrete cursor closes the gap between browser snapshot reads
                # and the first stream read after (re)connection.
                await self._connection(True)
                while True:
                    rows = cast(
                        list[tuple[str, list[tuple[str, dict[str, str]]]]],
                        await self._redis.xread({_STREAM: cursor}, block=1000, count=100),
                    )
                    for _, messages in rows:
                        for message_id, fields in messages:
                            cursor = message_id
                            event = self._read_event(fields)
                            if event is not None and event["type"] == "historyDownloadsResnapshot":
                                await self._connection(True)
                            elif event is not None:
                                await self._broadcast(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("History download event stream disconnected")
                await self._connection(False)
                await asyncio.sleep(1)

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        await self._redis.aclose()
