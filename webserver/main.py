import asyncio
import json
import logging
import os
import signal
import sys
from typing import Optional, Union

import websockets
from aiohttp import web
from algotrader_logger import bind_context, configure_logging
from app.broker_client import BrokerClient
from app.indicator_api_client import IndicatorApiClient
from app.redis_consumer import RedisConsumer
from app.subscription_manager import SubscriptionManager
from websockets.asyncio.server import ServerConnection

configure_logging(
    service_name="webserver",
    level=os.getenv("WEBSERVER_LOG_LEVEL", "INFO"),
    format=os.getenv("WEBSERVER_LOG_FORMAT", "pretty"),
)
logger = logging.getLogger(__name__)


class WebSocketServer:
    def __init__(self, config: dict):
        self.config = config
        self.broker_client: Optional[BrokerClient] = None
        self.indicator_api_client: Optional[IndicatorApiClient] = None
        self.redis_consumer: Optional[RedisConsumer] = None
        self.subscription_manager: Optional[SubscriptionManager] = None
        self.health_app: Optional[web.Application] = None
        self.health_runner: Optional[web.AppRunner] = None
        self._shutdown_lock = asyncio.Lock()
        self._is_shutdown = False

    async def initialize(self):
        self.broker_client = BrokerClient(
            self.config["broker_service_url"], self.config["account_id"]
        )

        self.indicator_api_client = IndicatorApiClient(
            self.config["indicator_api_url"],
            self.config["account_id"],
        )

        self.redis_consumer = RedisConsumer(
            redis_host=self.config["redis_host"],
            redis_port=self.config["redis_port"],
            account_id=self.config["account_id"],
            block_ms=self.config["redis_block_ms"],
            batch_size=self.config["redis_batch_size"],
        )

        self.subscription_manager = SubscriptionManager(
            self.broker_client,
            self.redis_consumer,
            self.indicator_api_client,
        )

        self.redis_consumer.subscription_manager = self.subscription_manager
        await self.redis_consumer.connect()

    async def handle_client(self, websocket: ServerConnection):
        assert self.subscription_manager is not None
        client_id = self.subscription_manager.register_client(websocket)
        logger.info("Client connected", extra={"event": "client_connected", "client_id": client_id})

        try:
            with bind_context(client_id=client_id):
                async for message_data in websocket:
                    try:
                        await self.handle_message(websocket, client_id, message_data)
                    except Exception as e:
                        logger.error("Error handling message: %s", e)
                        await websocket.send(json.dumps({"type": "error", "error": str(e)}))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.subscription_manager.unregister_client(client_id)

    async def handle_message(
        self, websocket: ServerConnection, client_id: int, message_data: Union[str, bytes]
    ):
        assert self.subscription_manager is not None
        if isinstance(message_data, bytes):
            message_data = message_data.decode("utf-8")
        message = json.loads(message_data)
        message_type = message.get("type")

        if message_type == "subscribeCandles":
            await self._handle_subscribe_candles_message(websocket, client_id, message)

        elif message_type == "unsubscribeCandles":
            await self._handle_unsubscribe_candles_message(client_id, message)

        elif message_type == "subscribeIndicator":
            await self._handle_subscribe_indicator_message(websocket, client_id, message)

        elif message_type == "unsubscribeIndicator":
            await self._handle_unsubscribe_indicator_message(websocket, client_id, message)

        else:
            logger.warning(f"Unknown message type: {message_type}")

    async def _handle_subscribe_candles_message(
        self,
        websocket: ServerConnection,
        client_id: int,
        message: dict,
    ) -> None:
        assert self.subscription_manager is not None
        symbol = message.get("symbol")
        timeframe = message.get("timeframe")

        if not symbol or not isinstance(timeframe, str):
            raise ValueError("Missing symbol or timeframe")

        await self.subscription_manager.subscribe_candles(client_id, symbol, timeframe)
        await websocket.send(
            json.dumps({"type": "subscribed", "symbol": symbol, "timeframe": timeframe})
        )

    async def _handle_unsubscribe_candles_message(
        self,
        client_id: int,
        message: dict,
    ) -> None:
        assert self.subscription_manager is not None
        symbol = message.get("symbol")
        timeframe = message.get("timeframe")

        if not symbol or not isinstance(timeframe, str):
            raise ValueError("Missing symbol or timeframe")

        await self.subscription_manager.unsubscribe_candles(client_id, symbol, timeframe)

    async def _handle_subscribe_indicator_message(
        self,
        websocket: ServerConnection,
        client_id: int,
        message: dict,
    ) -> None:
        assert self.subscription_manager is not None
        symbol = message.get("symbol")
        timeframe = message.get("timeframe")
        indicator_id = message.get("indicatorId")
        client_indicator_id = message.get("clientIndicatorId")
        parameters = message.get("parameters") or {}
        exchange = message.get("exchange")

        if (
            not symbol
            or not isinstance(timeframe, str)
            or indicator_id is None
            or client_indicator_id is None
        ):
            raise ValueError("Missing symbol, timeframe, indicatorId, or clientIndicatorId")

        result = await self.subscription_manager.subscribe_indicator(
            client_id=client_id,
            symbol=symbol,
            timeframe=timeframe,
            indicator_id=int(indicator_id),
            parameters=parameters,
            exchange=exchange,
            client_indicator_id=str(client_indicator_id),
        )
        await websocket.send(
            json.dumps(
                {
                    "type": "indicatorSubscribed",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "indicatorId": int(indicator_id),
                    "clientIndicatorId": str(client_indicator_id),
                    "streamId": result.get("stream_id"),
                }
            )
        )

    async def _handle_unsubscribe_indicator_message(
        self,
        websocket: ServerConnection,
        client_id: int,
        message: dict,
    ) -> None:
        assert self.subscription_manager is not None
        symbol = message.get("symbol")
        timeframe = message.get("timeframe")
        indicator_id = message.get("indicatorId")
        client_indicator_id = message.get("clientIndicatorId")
        parameters = message.get("parameters") or {}
        exchange = message.get("exchange")

        if (
            not symbol
            or not isinstance(timeframe, str)
            or indicator_id is None
            or client_indicator_id is None
        ):
            raise ValueError("Missing symbol, timeframe, indicatorId, or clientIndicatorId")

        await self.subscription_manager.unsubscribe_indicator(
            client_id=client_id,
            symbol=symbol,
            timeframe=timeframe,
            indicator_id=int(indicator_id),
            parameters=parameters,
            exchange=exchange,
            client_indicator_id=str(client_indicator_id),
        )

        await websocket.send(
            json.dumps(
                {
                    "type": "indicatorUnsubscribed",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "indicatorId": int(indicator_id),
                    "clientIndicatorId": str(client_indicator_id),
                }
            )
        )

    async def health_handler(self, request):
        return web.Response(text='{"status": "healthy"}', content_type="application/json")

    async def start_health_server(self):
        self.health_app = web.Application()
        self.health_app.router.add_get("/health", self.health_handler)

        self.health_runner = web.AppRunner(self.health_app)
        await self.health_runner.setup()

        health_port = self.config.get("health_port", 8080)
        site = web.TCPSite(self.health_runner, "0.0.0.0", health_port)
        await site.start()
        logger.info(f"Health check server running on port {health_port}")

    async def start(self, stop_event: asyncio.Event):
        await self.initialize()
        await self.start_health_server()

        try:
            async with websockets.serve(self.handle_client, "0.0.0.0", self.config["ws_port"]):
                logger.info(f"WebSocket server running on port {self.config['ws_port']}")
                await stop_event.wait()
                logger.info("Shutdown signal received, stopping WebSocket server")
        finally:
            await self.shutdown()

    async def shutdown(self):
        async with self._shutdown_lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True

            if self.health_runner:
                await self.health_runner.cleanup()
                self.health_runner = None

            if self.redis_consumer:
                await self.redis_consumer.disconnect()
                self.redis_consumer = None

            if self.indicator_api_client:
                await self.indicator_api_client.close()
                self.indicator_api_client = None

            if self.broker_client:
                await self.broker_client.close()
                self.broker_client = None


async def main():
    broker_host = os.getenv("BROKER_SERVICE_HOST", "broker-service")
    broker_port = int(os.getenv("BROKER_SERVICE_PORT", "8050"))
    broker_service_url = os.getenv(
        "BROKER_SERVICE_BASE_URL",
        f"http://{broker_host}:{broker_port}",
    )

    indicator_host = os.getenv("INDICATOR_API_HOST", "indicator-api")
    indicator_port = int(os.getenv("INDICATOR_API_PORT", "8010"))
    indicator_api_url = os.getenv(
        "INDICATOR_API_BASE_URL",
        f"http://{indicator_host}:{indicator_port}",
    )

    config = {
        "ws_port": int(os.getenv("WEBSERVER_WS_PORT", "8765")),
        "health_port": int(os.getenv("WEBSERVER_HEALTH_PORT", "8080")),
        "redis_host": os.getenv("REDIS_HOST", "redis"),
        "redis_port": int(os.getenv("REDIS_PORT", "6379")),
        "broker_service_url": broker_service_url,
        "indicator_api_url": indicator_api_url,
        "account_id": os.getenv("ACCOUNT_ID"),
        "redis_block_ms": int(os.getenv("WEBSERVER_REDIS_BLOCK_MS", "5000")),
        "redis_batch_size": int(os.getenv("WEBSERVER_REDIS_BATCH_SIZE", "100")),
    }

    if not config["account_id"]:
        logger.error("ACCOUNT_ID environment variable required")
        sys.exit(1)

    server = WebSocketServer(config)

    stop_event = asyncio.Event()

    def signal_handler():
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await server.start(stop_event)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        await server.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as exc:
        if str(exc) == "Event loop stopped before Future completed.":
            logger.info("Event loop stopped during shutdown; exiting cleanly")
        else:
            raise
