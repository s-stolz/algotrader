"""Bound transport liveness independently of Market activity."""

import logging
from typing import Any, override

from ctrader_open_api import TcpProtocol
from twisted.internet import reactor
from twisted.internet.interfaces import IDelayedCall

logger = logging.getLogger(__name__)


class CtraderProtocol(TcpProtocol):
    # The SDK sends heartbeats every 20 seconds, including while Markets are closed.
    receive_timeout_seconds = 60
    _receive_timeout: IDelayedCall | None = None

    @override
    def connectionMade(self) -> None:
        super().connectionMade()
        self._arm_receive_timeout()

    @override
    def stringReceived(self, data: bytes) -> bytes:
        result = super().stringReceived(data)
        self._arm_receive_timeout()
        return result

    @override
    def connectionLost(self, reason: Any) -> None:
        self._cancel_receive_timeout()
        super().connectionLost(reason)

    def _cancel_receive_timeout(self) -> None:
        if self._receive_timeout is not None and self._receive_timeout.active():
            self._receive_timeout.cancel()
        self._receive_timeout = None

    def _arm_receive_timeout(self) -> None:
        self._cancel_receive_timeout()
        self._receive_timeout = reactor.callLater(  # type: ignore[attr-defined]
            self.receive_timeout_seconds, self._abort_unresponsive_transport
        )

    def _abort_unresponsive_transport(self) -> None:
        self._receive_timeout = None
        logger.warning(
            "No cTrader protocol responses for %s seconds; resetting transport",
            self.receive_timeout_seconds,
        )
        self.transport.abortConnection()
