"""
Base handler class for websocket message handlers.
"""
import logging
from abc import ABC, abstractmethod
from src.utils.ticket import Ticket


class BaseHandler(ABC):
    """Base class for all message handlers."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def can_handle(self, message_type: str) -> bool:
        """Check if this handler can process the given message type."""
        pass

    @abstractmethod
    async def handle(self, message: dict, websocket) -> None:
        """Handle the message and send response if needed."""
        pass

    async def send_response(self, websocket, response_data: dict) -> None:
        """Send a response back through the websocket."""
        response = Ticket().from_object(response_data)
        self.logger.info(f"Sending: {response}")
        await websocket.send(response)

    def log_received(self, message: dict) -> None:
        """Log received message."""
        self.logger.info(
            f"Handling message type: {message.get('type', 'unknown')}")
