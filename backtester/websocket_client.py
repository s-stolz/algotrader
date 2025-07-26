import asyncio
import websockets
import logging
from src.utils.ticket import Ticket
from src.handlers import MessageDispatcher, IndicatorHandler


class WebSocketClient:
    def __init__(self, uri: str = "ws://backend:8765"):
        self.uri = uri
        self.dispatcher = MessageDispatcher()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        self.dispatcher.register_handler(IndicatorHandler())

    async def connect_and_run(self) -> None:
        while True:
            try:
                await self._connect()

            except (ConnectionRefusedError, OSError) as e:
                self.logger.warning(f"Connection failed: {e}")
                self.logger.info("Retrying in 5 seconds...")
                await asyncio.sleep(5)

    async def _connect(self) -> None:
        self.logger.info(
            f'Attempting to connect...')

        async with websockets.connect(self.uri) as websocket:
            self.logger.info("Connected to server")

            await self._send_login(websocket)

            async for message in websocket:
                await self.dispatcher.dispatch(message, websocket)

    async def _send_login(self, websocket) -> None:
        message = Ticket().from_object({
            'receiver': 'Broker',
            'type': 'Login'
        })
        await websocket.send(message)
        self.logger.info(f"Sent login: {message}")

    def run_in_thread(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.connect_and_run())
