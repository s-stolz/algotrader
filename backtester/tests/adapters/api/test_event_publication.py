import unittest
from unittest.mock import Mock

from adapters.api.app import create_app
from adapters.backtest_events import BacktestEventPublisher
from fastapi import HTTPException
from fastapi.testclient import TestClient


class PublicationTests(unittest.TestCase):
    def test_success_and_ambiguous_failure_schedule_reconciliation_but_reads_do_not(self):
        events = Mock(spec=BacktestEventPublisher)
        app = create_app(events=events)

        @app.post("/backtests/test-commit")
        def commit():
            return {"status": "cancelling"}

        @app.post("/backtests/test-ambiguous")
        def ambiguous():
            raise HTTPException(503, "Storage response lost")

        with TestClient(app) as client:
            self.assertEqual(client.post("/backtests/test-commit").status_code, 200)
            self.assertEqual(client.post("/backtests/test-ambiguous").status_code, 503)
            self.assertEqual(client.get("/health").status_code, 200)
        events.start.assert_called_once()
        events.close.assert_called_once()
        self.assertEqual(events.changed.call_count, 2)
