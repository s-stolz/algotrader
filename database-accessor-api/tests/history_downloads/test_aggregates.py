import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.history_downloads.aggregates import refresh_inserted_history


class AggregateConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_failure_and_cancellation_discard_connection_without_hiding_original_error(self):
        for failure_type in (RuntimeError, asyncio.CancelledError):
            for cleanup_fails in (False, True):
                with self.subTest(failure=failure_type.__name__, cleanup_fails=cleanup_fails):
                    failure = failure_type("refresh interrupted")
                    connection = SimpleNamespace(invalidate=AsyncMock())
                    connection.execution_options = AsyncMock(return_value=connection)
                    if cleanup_fails:
                        connection.invalidate.side_effect = RuntimeError(
                            "connection cleanup failed"
                        )
                    context = MagicMock()
                    context.__aenter__ = AsyncMock(return_value=connection)
                    context.__aexit__ = AsyncMock(return_value=False)
                    session = SimpleNamespace(
                        get_bind=lambda: SimpleNamespace(
                            dialect=SimpleNamespace(name="postgresql")
                        ),
                        bind=SimpleNamespace(connect=lambda: context),
                    )
                    with patch(
                        "app.history_downloads.aggregates.refresh_views",
                        new=AsyncMock(side_effect=failure),
                    ):
                        with self.assertRaises(failure_type) as raised:
                            await refresh_inserted_history(session, {"first_inserted_ms": 60000})
                    self.assertIs(raised.exception, failure)
                    connection.invalidate.assert_awaited_once()
