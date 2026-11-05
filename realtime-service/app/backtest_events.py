"""Fan out backtest invalidations and health on the shared browser socket."""

import asyncio
import json
import logging

from redis.asyncio import Redis

_LOGGER = logging.getLogger(__name__)
_STREAM = "backtests:events:v1"


class BacktestEventBridge:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._clients: set = set()
        self._connected = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def subscribe(self, websocket) -> None:
        self._clients.add(websocket)
        await websocket.send(
            json.dumps({"type": "backtestConnection", "connected": self._connected})
        )

    def unsubscribe(self, websocket) -> None:
        self._clients.discard(websocket)

    async def _send(self, websocket, payload: str) -> None:
        try:
            await asyncio.wait_for(websocket.send(payload), timeout=5)
        except Exception:
            self._clients.discard(websocket)
            await websocket.close()

    async def _broadcast(self, message: dict) -> None:
        payload = json.dumps(message)
        await asyncio.gather(*(self._send(client, payload) for client in list(self._clients)))

    async def _connection(self, connected: bool) -> None:
        self._connected = connected
        await self._broadcast({"type": "backtestConnection", "connected": connected})

    async def _run(self) -> None:
        while True:
            try:
                # Establish a concrete cursor before advertising continuity. Every
                # subscriber refreshes a snapshot on (re)connection; old events
                # need not be replayed into browser state.
                tail = await self._redis.xrevrange(_STREAM, count=1)
                cursor = tail[0][0] if tail else "0-0"
                await self._connection(True)
                while True:
                    rows = await self._redis.xread({_STREAM: cursor}, block=1000, count=100)
                    for _, messages in rows:
                        for message_id, fields in messages:
                            message = json.loads(fields["payload"])
                            if message.get("type") in {"backtestChanged", "backtestHealth"}:
                                await self._broadcast(message)
                            cursor = message_id
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("Backtest event stream disconnected")
                await self._connection(False)
                await asyncio.sleep(1)

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        await self._redis.aclose()
