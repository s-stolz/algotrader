"""End-to-end smoke runner behavior tests."""

from __future__ import annotations

import unittest

import smoke


class _Response:
    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> object:
        return self._payload


class _StorageClient:
    def __init__(self) -> None:
        self.seeded_candles: list[dict[str, object]] = []

    def get(self, path: str, **kwargs: object) -> _Response:
        self.assert_path(path, "/markets")
        return _Response(payload=[])

    def post(self, path: str, **kwargs: object) -> _Response:
        if path == "/markets":
            return _Response(payload={"symbol_id": 1, "status": "created"})
        self.assert_path(path, "/candles")
        payload = kwargs["json"]
        assert isinstance(payload, dict)
        candles = payload["candles"]
        assert isinstance(candles, list)
        self.seeded_candles = candles
        return _Response(payload={"status": "ok", "added_candles": len(candles)})

    def delete(self, path: str, **kwargs: object) -> _Response:
        self.assert_path(path, f"/markets/{smoke.FIXTURE_SYMBOL}")
        return _Response(payload={"status": "deleted"})

    def close(self) -> None:
        return None

    def assert_path(self, actual: str, expected: str) -> None:
        if actual != expected:
            raise AssertionError(f"Expected {expected}, got {actual}")


class _BacktesterClient:
    def __init__(self) -> None:
        self.submission_count = 0
        self.success_reads = 0
        self.deleted_runs: list[str] = []

    def post(self, path: str, **kwargs: object) -> _Response:
        if path != "/backtests":
            raise AssertionError(f"Unexpected POST {path}")
        self.submission_count += 1
        run_id = "run-success" if self.submission_count == 1 else "run-failure"
        return _Response(
            status_code=202,
            payload={"run_id": run_id, "status": "queued"},
            headers={"location": f"/backtests/{run_id}"},
        )

    def get(self, path: str, **kwargs: object) -> _Response:
        if path == "/backtests/run-success":
            self.success_reads += 1
            if self.success_reads == 1:
                return _Response(payload={"run_id": "run-success", "status": "running"})
            return _Response(
                payload={
                    "run_id": "run-success",
                    "status": "succeeded",
                    "metrics": {"trade_count": 1.0},
                    "diagnostics": {"bars": 9},
                }
            )
        if path == "/backtests/run-success/fills":
            return _Response(payload=[{"sequence": 0, "side": "buy"}])
        if path == "/backtests/run-success/trades":
            return _Response(payload=[{"sequence": 0, "realized_pnl": 3.0}])
        if path == "/backtests/run-failure":
            return _Response(
                payload={
                    "run_id": "run-failure",
                    "status": "failed",
                    "error_code": "backtest_failed",
                    "error_message": "Backtest execution failed",
                }
            )
        if path in {
            "/backtests/run-failure/fills",
            "/backtests/run-failure/trades",
        }:
            return _Response(payload=[])
        raise AssertionError(f"Unexpected GET {path}")

    def delete(self, path: str, **kwargs: object) -> _Response:
        self.deleted_runs.append(path.rsplit("/", 1)[-1])
        return _Response(status_code=204)

    def close(self) -> None:
        return None


class TestBacktesterSmokeRunner(unittest.TestCase):
    def test_success_and_failure_lifecycle_paths(self) -> None:
        backtester_client = _BacktesterClient()
        storage_client = _StorageClient()

        report = smoke.run_smoke(
            backtester_client=backtester_client,
            storage_client=storage_client,
            timeout_seconds=1.0,
            poll_interval_seconds=0.0,
            sleep=lambda _: None,
            failure_symbol="SMKFAIL001",
        )

        self.assertEqual(report.success_statuses, ("queued", "running", "succeeded"))
        self.assertEqual(report.success_fill_count, 1)
        self.assertEqual(report.success_trade_count, 1)
        self.assertEqual(report.failure_status, "failed")
        self.assertEqual(report.failure_fill_count, 0)
        self.assertEqual(report.failure_trade_count, 0)
        self.assertGreater(len(storage_client.seeded_candles), 3)
        self.assertEqual(backtester_client.deleted_runs, ["run-success", "run-failure"])


if __name__ == "__main__":
    unittest.main()
