import unittest

import numpy as np

from indicator_engine.core.bars import BarTensor
from indicator_engine.core.history import HistoryPolicy
from indicator_engine.core.registry import IndicatorRegistry
from indicator_engine.core.spec import IndicatorSpec
from indicator_engine.core.tensor import Tensor
from indicator_engine.engines.update import UpdateEngine


class LastCloseIndicator:
    spec = IndicatorSpec(
        id="test_last_close",
        name="Test Last Close",
        outputs=["value"],
        required_fields=["close"],
        supports_update=False,
        supports_vectorized=False,
        warmup_fn=lambda params: 1,
    )

    def batch(self, data: BarTensor, params: dict) -> Tensor:
        close_idx = int(np.where(data.fields == "close")[0][0])
        values = data.data[:, :, close_idx][:, :, np.newaxis]
        return Tensor(
            data=values,
            dims=("time", "asset", "output"),
            coords={
                "time": data.time,
                "asset": data.assets,
                "output": np.array(["value"], dtype=object),
            },
        )


class RequiredAssetsIndicator(LastCloseIndicator):
    spec = IndicatorSpec(
        id="test_required_assets",
        name="Test Required Assets",
        outputs=["value"],
        required_fields=["close"],
        required_assets=["A", "B"],
        supports_update=False,
        supports_vectorized=False,
        warmup_fn=lambda params: 1,
    )


class UpdateEngineTests(unittest.TestCase):
    def _registry(self) -> IndicatorRegistry:
        registry = IndicatorRegistry()
        registry.register(LastCloseIndicator())
        registry.register(RequiredAssetsIndicator())
        return registry

    def _required_row(self, a: float | None = None, b: float | None = None) -> np.ndarray:
        return np.array(
            [
                [np.nan if a is None else a],
                [np.nan if b is None else b],
            ],
            dtype=np.float64,
        )

    def test_waits_for_required_assets_before_emitting(self) -> None:
        engine = UpdateEngine(self._registry(), HistoryPolicy(mode="rolling", max_rows=10))
        engine.register_indicator(
            indicator_id="test_required_assets",
            timeframe="M1",
            assets=["A", "B"],
            fields=["close"],
        )

        first = engine.on_bar(
            timeframe="M1",
            timestamp_ms=1000,
            new_row=self._required_row(a=1.0),
            asset_mask=np.array([True, False]),
        )
        self.assertNotIn("test_required_assets", first)

        second = engine.on_bar(
            timeframe="M1",
            timestamp_ms=1000,
            new_row=self._required_row(b=2.0),
            asset_mask=np.array([False, True]),
        )
        self.assertIn("test_required_assets", second)

    def test_partial_same_timestamp_does_not_duplicate_rows(self) -> None:
        engine = UpdateEngine(self._registry(), HistoryPolicy(mode="rolling", max_rows=10))
        engine.register_indicator(
            indicator_id="test_required_assets",
            timeframe="M1",
            assets=["A", "B"],
            fields=["close"],
        )

        engine.on_bar(
            timeframe="M1",
            timestamp_ms=1000,
            new_row=self._required_row(a=1.0),
            asset_mask=np.array([True, False]),
        )
        engine.on_bar(
            timeframe="M1",
            timestamp_ms=1000,
            new_row=self._required_row(b=2.0),
            asset_mask=np.array([False, True]),
        )

        bar_view = engine._bar_buffers["M1"].view()
        self.assertEqual(bar_view.time.tolist(), [1000])
        self.assertAlmostEqual(bar_view.data[0, 0, 0], 1.0)
        self.assertAlmostEqual(bar_view.data[0, 1, 0], 2.0)

        result_view = engine.get_result_buffer("test_required_assets", "M1").view()
        self.assertEqual(result_view.coords["time"].tolist(), [1000])

    def test_out_of_order_rejected_by_default(self) -> None:
        engine = UpdateEngine(self._registry(), HistoryPolicy(mode="rolling", max_rows=10))
        engine.register_indicator(
            indicator_id="test_last_close",
            timeframe="M1",
            assets=["A"],
            fields=["close"],
        )

        engine.on_bar(
            timeframe="M1",
            timestamp_ms=2000,
            new_row=np.array([[2.0]], dtype=np.float64),
        )

        with self.assertRaisesRegex(ValueError, "Out-of-order"):
            engine.on_bar(
                timeframe="M1",
                timestamp_ms=1000,
                new_row=np.array([[1.0]], dtype=np.float64),
            )

    def test_out_of_order_allowed_when_enabled(self) -> None:
        engine = UpdateEngine(self._registry(), HistoryPolicy(mode="rolling", max_rows=10))
        engine.register_indicator(
            indicator_id="test_last_close",
            timeframe="M1",
            assets=["A"],
            fields=["close"],
            allow_out_of_order=True,
        )

        engine.on_bar(
            timeframe="M1",
            timestamp_ms=2000,
            new_row=np.array([[2.0]], dtype=np.float64),
        )
        updated = engine.on_bar(
            timeframe="M1",
            timestamp_ms=1000,
            new_row=np.array([[1.0]], dtype=np.float64),
        )

        self.assertIn("test_last_close", updated)
        self.assertEqual(engine._bar_buffers["M1"].view().time.tolist(), [2000, 1000])

    def test_pending_evicted_by_max_delay_bars(self) -> None:
        engine = UpdateEngine(
            self._registry(),
            HistoryPolicy(mode="rolling", max_rows=10),
            max_delay_bars=1,
        )
        engine.register_indicator(
            indicator_id="test_required_assets",
            timeframe="M1",
            assets=["A", "B"],
            fields=["close"],
        )

        engine.on_bar("M1", 1000, self._required_row(a=1.0), asset_mask=np.array([True, False]))
        engine.on_bar("M1", 2000, self._required_row(a=2.0), asset_mask=np.array([True, False]))
        engine.on_bar("M1", 3000, self._required_row(a=3.0), asset_mask=np.array([True, False]))

        pending = engine._registrations["M1"][0].pending
        self.assertNotIn(1000, pending)
        self.assertIn(2000, pending)
        self.assertIn(3000, pending)

    def test_pending_evicted_by_max_delay_ms(self) -> None:
        engine = UpdateEngine(
            self._registry(),
            HistoryPolicy(mode="rolling", max_rows=10),
            max_delay_ms=1500,
        )
        engine.register_indicator(
            indicator_id="test_required_assets",
            timeframe="M1",
            assets=["A", "B"],
            fields=["close"],
        )

        engine.on_bar("M1", 1000, self._required_row(a=1.0), asset_mask=np.array([True, False]))
        engine.on_bar("M1", 2000, self._required_row(a=2.0), asset_mask=np.array([True, False]))
        engine.on_bar("M1", 3001, self._required_row(a=3.0), asset_mask=np.array([True, False]))

        pending = engine._registrations["M1"][0].pending
        self.assertNotIn(1000, pending)
        self.assertIn(2000, pending)
        self.assertIn(3001, pending)

    def test_pending_evicted_when_bar_buffer_rolls_past_timestamp(self) -> None:
        engine = UpdateEngine(
            self._registry(),
            HistoryPolicy(mode="rolling", max_rows=2),
        )
        engine.register_indicator(
            indicator_id="test_required_assets",
            timeframe="M1",
            assets=["A", "B"],
            fields=["close"],
        )

        engine.on_bar("M1", 1000, self._required_row(a=1.0), asset_mask=np.array([True, False]))
        engine.on_bar("M1", 2000, self._required_row(a=2.0), asset_mask=np.array([True, False]))
        engine.on_bar("M1", 3000, self._required_row(a=3.0), asset_mask=np.array([True, False]))

        pending = engine._registrations["M1"][0].pending
        self.assertNotIn(1000, pending)
        self.assertIn(2000, pending)
        self.assertIn(3000, pending)

    def test_unbounded_history_grows_and_preserves_order(self) -> None:
        engine = UpdateEngine(
            self._registry(),
            HistoryPolicy(mode="unbounded", max_rows=2),
        )
        engine.register_indicator(
            indicator_id="test_last_close",
            timeframe="M1",
            assets=["A"],
            fields=["close"],
        )

        engine.on_bar("M1", 1000, np.array([[1.0]], dtype=np.float64))
        engine.on_bar("M1", 2000, np.array([[2.0]], dtype=np.float64))
        engine.on_bar("M1", 3000, np.array([[3.0]], dtype=np.float64))

        bar_buffer = engine._bar_buffers["M1"]
        self.assertGreaterEqual(bar_buffer.capacity, 4)
        self.assertEqual(bar_buffer.view().time.tolist(), [1000, 2000, 3000])

        result = engine.get_result_buffer("test_last_close", "M1")
        result_view = result.view()
        self.assertEqual(result_view.coords["time"].tolist(), [1000, 2000, 3000])
        self.assertGreaterEqual(len(result_view.coords["time"]), 3)
        np.testing.assert_allclose(result_view.data[:, 0, 0, 0], np.array([1.0, 2.0, 3.0]))


if __name__ == "__main__":
    unittest.main()
