import unittest
from importlib import import_module
from unittest.mock import Mock, patch

from app.infrastructure.ctrader_protocol import CtraderProtocol
from twisted.internet.task import Clock
from twisted.internet.testing import StringTransport

common_messages = import_module("ctrader_open_api.messages.OpenApiCommonMessages_pb2")
ProtoHeartbeatEvent = getattr(common_messages, "ProtoHeartbeatEvent")
ProtoMessage = getattr(common_messages, "ProtoMessage")


class CtraderProtocolTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.patch = patch("app.infrastructure.ctrader_protocol.reactor", self.clock)
        self.patch.start()
        self.protocol = CtraderProtocol()
        self.protocol.factory = Mock()
        self.transport = StringTransport()
        self.protocol.makeConnection(self.transport)

    def tearDown(self):
        self.protocol.connectionLost(None)
        self.patch.stop()

    def test_missing_protocol_responses_aborts_transport(self):
        self.clock.advance(59)
        self.assertFalse(self.transport.disconnecting)
        self.clock.advance(1)
        self.assertTrue(self.transport.disconnecting)

    def test_heartbeats_keep_quiet_markets_connected(self):
        message = ProtoMessage(payloadType=ProtoHeartbeatEvent().payloadType).SerializeToString()
        for _ in range(10):
            self.clock.advance(20)
            self.protocol.stringReceived(message)
        self.assertFalse(self.transport.disconnecting)

    def test_disconnect_cancels_watchdog(self):
        self.protocol.connectionLost(None)
        self.clock.advance(120)
        self.assertFalse(self.transport.disconnecting)
        self.assertFalse(self.clock.getDelayedCalls())
