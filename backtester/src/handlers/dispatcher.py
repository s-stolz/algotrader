"""
Message dispatcher to route messages to appropriate handlers.
"""
import json
import logging
from typing import List
from .base import BaseHandler


class MessageDispatcher:
    """Dispatcher to route messages to appropriate handlers."""

    def __init__(self):
        self.handlers: List[BaseHandler] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_handler(self, handler: BaseHandler) -> None:
        """Register a message handler."""
        self.handlers.append(handler)
        self.logger.info(f"Registered handler: {handler.__class__.__name__}")

    async def dispatch(self, raw_message: str, websocket) -> None:
        """Dispatch a message to the appropriate handler."""
        try:
            self.logger.info(f"Received raw message: {raw_message}")
            message = json.loads(raw_message)
            message_type = message.get('type')

            if not message_type:
                self.logger.warning("Message has no type field")
                return

            handler = self.find_handler(message_type)
            if handler is None:
                self.logger.warning(
                    f"No handler found for message type: {message_type}"
                )
                return

            await handler.handle(message, websocket)

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON message: {e}")
        except Exception as e:
            self.logger.error(f"Error dispatching message: {e}")

    def find_handler(self, message_type: str) -> BaseHandler:
        """Find a handler that can process the given message type."""
        for handler in self.handlers:
            if handler.can_handle(message_type):
                return handler
        return None
