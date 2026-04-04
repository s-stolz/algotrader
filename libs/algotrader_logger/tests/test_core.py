from __future__ import annotations

import io
import json
import logging
import unittest

from algotrader_logger import bind_context, configure_logging, get_logger
from algotrader_logger.core import ServiceContextFilter


class LoggerCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        logging.getLogger().handlers.clear()

    def test_pretty_format_includes_context(self) -> None:
        stream = io.StringIO()
        configure_logging(
            service_name="test-service",
            level="INFO",
            format="pretty",
            stream=stream,
        )

        logger = get_logger("tests.pretty")
        with bind_context(request_id="abc123"):
            logger.info("hello", extra={"symbol": "EURUSD"})

        line = stream.getvalue().strip()
        self.assertIn("hello", line)
        self.assertIn('request_id="abc123"', line)
        self.assertIn('symbol="EURUSD"', line)

    def test_json_format_is_valid_json(self) -> None:
        stream = io.StringIO()
        configure_logging(
            service_name="test-service",
            level="INFO",
            format="json",
            stream=stream,
        )

        logger = get_logger("tests.json")
        logger.info("payload", extra={"event": "unit_test"})

        payload = json.loads(stream.getvalue().strip())
        self.assertEqual(payload["service"], "test-service")
        self.assertEqual(payload["logger"], "tests.json")
        self.assertEqual(payload["message"], "payload")
        self.assertEqual(payload["event"], "unit_test")

    def test_healthcheck_access_log_is_suppressed(self) -> None:
        record_health = logging.makeLogRecord(
            {
                "name": "uvicorn.access",
                "levelno": logging.INFO,
                "levelname": "INFO",
                "msg": '%s - "%s %s HTTP/%s" %d',
                "args": ("127.0.0.1", "GET", "/health", "1.1", 200),
            }
        )
        record_normal = logging.makeLogRecord(
            {
                "name": "uvicorn.access",
                "levelno": logging.INFO,
                "levelname": "INFO",
                "msg": '%s - "%s %s HTTP/%s" %d',
                "args": ("127.0.0.1", "GET", "/markets", "1.1", 200),
            }
        )
        log_filter = ServiceContextFilter(service_name="test-service", suppress_healthcheck_logs=True)
        self.assertFalse(log_filter.filter(record_health))
        self.assertTrue(log_filter.filter(record_normal))

    def test_sensitive_field_is_redacted(self) -> None:
        stream = io.StringIO()
        configure_logging(
            service_name="test-service",
            level="INFO",
            format="json",
            stream=stream,
        )

        logger = get_logger("tests.redaction")
        logger.info("auth", extra={"access_token": "plain-secret-token"})

        payload = json.loads(stream.getvalue().strip())
        self.assertEqual(payload["access_token"], "***")

    def test_debug_formatting_is_lazy_when_disabled(self) -> None:
        stream = io.StringIO()
        configure_logging(
            service_name="test-service",
            level="INFO",
            format="pretty",
            stream=stream,
        )

        class ExpensiveObject:
            def __init__(self) -> None:
                self.calls = 0

            def __str__(self) -> str:
                self.calls += 1
                return "expensive"

        value = ExpensiveObject()
        logger = get_logger("tests.perf")
        logger.debug("payload=%s", value)
        self.assertEqual(value.calls, 0)

    def test_pretty_can_be_colorized(self) -> None:
        stream = io.StringIO()
        configure_logging(
            service_name="test-service",
            level="INFO",
            format="pretty",
            stream=stream,
            colorize=True,
        )
        logger = get_logger("tests.color")
        logger.info("color test")
        line = stream.getvalue().strip()
        self.assertIn("\x1b[32mINFO\x1b[0m", line)


if __name__ == "__main__":
    unittest.main()
