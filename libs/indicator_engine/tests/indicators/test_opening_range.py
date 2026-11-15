import unittest

import numpy as np
from indicator_engine import (
    BarTensor,
    BatchEngine,
    HistoryPolicy,
    ParamGrid,
    UpdateEngine,
    get_registry,
)
from indicator_engine.indicators.opening_range import OpeningRange

DAY = 86_400_000
MINUTE = 60_000
START = 20000 * DAY
PARAMS = {"start_time": "09:00", "end_time": "09:15", "extension_end_time": "12:00"}


def bars():
    times = START + np.array([535, 540, 545, 550, 555, 560]) * MINUTE
    first = np.array([[99, 1], [10, 4], [12, 3], [11, 5], [200, -100], [300, -200]], dtype=float)
    return BarTensor(
        np.stack([first, first + 10], axis=1),
        times,
        np.array(["A", "B"]),
        np.array(["high", "low"]),
    )


class OpeningRangeTests(unittest.TestCase):
    def test_develops_freezes_and_excludes_cutoff_candle(self):
        result = OpeningRange().batch(bars(), PARAMS)
        np.testing.assert_allclose(result.data[:, 0, 0], [0, 10, 12, 12, 12, 12])
        np.testing.assert_allclose(result.data[:, 0, 1], [0, 4, 3, 3, 3, 3])
        np.testing.assert_allclose(result.data[:, 0, 2], [0, 0, 0, 0, 1, 1])
        np.testing.assert_allclose(
            result.data[:, 0, 3:],
            np.tile([START + 540 * MINUTE, START + 555 * MINUTE, START + 720 * MINUTE], (6, 1)),
        )

    def test_batch_is_causal(self):
        data = bars()
        full = OpeningRange().batch(data, PARAMS)
        for length in range(1, len(data.time)):
            prefix = BarTensor(data.data[:length], data.time[:length], data.assets, data.fields)
            np.testing.assert_allclose(
                OpeningRange().batch(prefix, PARAMS).data, full.data[:length]
            )

    def test_daily_reset_does_not_reuse_previous_range(self):
        first = bars()
        data = BarTensor(
            np.concatenate([first.data, first.data + 50]),
            np.concatenate([first.time, first.time + DAY]),
            first.assets,
            first.fields,
        )
        result = OpeningRange().batch(data, PARAMS).data
        self.assertEqual(result[6, 0, 0], 0)
        self.assertEqual(result[6, 0, 2], 0)
        self.assertEqual(result[-1, 0, 0], 62)
        self.assertEqual(result[-1, 0, 2], 1)

    def test_invalid_prices_only_poison_the_formation_window(self):
        data = bars()
        data.data[[0, 4, 5]] = np.nan
        result = OpeningRange().batch(data, PARAMS).data
        self.assertEqual(result[-1, 0, 0], 12)
        self.assertEqual(result[-1, 0, 2], 1)
        data.data[2, 0] = [2, 3]
        result = OpeningRange().batch(data, PARAMS).data
        self.assertTrue(np.isnan(result[-1, 0, :2]).all())
        self.assertEqual(result[-1, 0, 2], 0)
        self.assertEqual(result[-1, 1, 2], 1)

    def test_missing_start_candle_never_marks_a_partial_range_ready(self):
        data = bars()
        selected = np.array([0, 2, 3, 4, 5])
        result = OpeningRange().batch(
            BarTensor(data.data[selected], data.time[selected], data.assets, data.fields), PARAMS
        )
        self.assertEqual(result.data[-1, 0, 2], 0)

    def test_configurable_zone_follows_daylight_saving_time(self):
        data = bars()
        for day, utc_hour in [("2026-03-27", 9), ("2026-03-30", 8)]:
            midnight = int(np.datetime64(day, "ms").astype(np.int64))
            times = midnight + utc_hour * 60 * MINUTE + np.arange(-1, 5) * 5 * MINUTE
            zoned = BarTensor(data.data, times, data.assets, data.fields)
            result = OpeningRange().batch(zoned, {**PARAMS, "timezone": "Europe/London"}).data
            self.assertEqual(result[-1, 0, 0], 12)
            self.assertEqual(result[-1, 0, 3], midnight + utc_hour * 60 * MINUTE)
            self.assertEqual(result[-1, 0, 2], 1)

    def test_history_resolves_zone_and_formation_window(self):
        spec = OpeningRange.spec
        noon = int(np.datetime64("2026-03-30T12:00", "ms").astype(np.int64))
        params = {**PARAMS, "timezone": "Europe/London"}
        plan = spec.plan_history(start_ms=noon, params=params)
        self.assertEqual(
            plan.start_ms, int(np.datetime64("2026-03-29T23:00", "ms").astype(np.int64))
        )
        self.assertEqual(plan.predecessor_bars, 0)
        self.assertEqual(spec.resolve_input_history(params).session.start_minute, 540)

    def test_invalid_clock_parameters_fail_before_computation(self):
        for params in [
            {"start_time": "9:00"},
            {"end_time": "24:01"},
            {"start_time": "09:00", "end_time": "08:00"},
            {"extension_end_time": "00:30"},
            {"timezone": 1},
        ]:
            with self.subTest(params=params), self.assertRaises(ValueError):
                OpeningRange().batch(bars(), params)

    def test_stream_matches_batch_with_small_buffer_and_partial_asset_arrivals(self):
        data = bars()
        data = BarTensor(
            np.concatenate([data.data, data.data + 20]),
            np.concatenate([data.time, data.time + DAY]),
            data.assets,
            data.fields,
        )
        engine = self._engine(data)
        values = []
        for timestamp, row in zip(data.time, data.data, strict=True):
            engine.on_bar(
                "M5", int(timestamp), np.array([row[0], [np.nan, np.nan]]), np.array([True, False])
            )
            result = engine.on_bar(
                "M5", int(timestamp), np.array([[np.nan, np.nan], row[1]]), np.array([False, True])
            )
            values.append(result["opening_range"].data[0])
        expected = BatchEngine(get_registry()).run("opening_range", data, ParamGrid(PARAMS)).tensor
        np.testing.assert_allclose(values, expected.data)

    def test_candle_corrections_replace_extremes_instead_of_accumulating_them(self):
        data = bars()
        engine = self._engine(data)
        for index, timestamp in enumerate(data.time):
            engine.on_bar("M5", int(timestamp), data.data[index] + 100)
            result = engine.on_bar("M5", int(timestamp), data.data[index])["opening_range"]
            prefix = BarTensor(
                data.data[: index + 1], data.time[: index + 1], data.assets, data.fields
            )
            np.testing.assert_allclose(
                result.data[0, :, :, 0], OpeningRange().batch(prefix, PARAMS).data[-1]
            )

    def _engine(self, data):
        engine = UpdateEngine(get_registry(), HistoryPolicy(mode="rolling", max_rows=1))
        engine.register_indicator(
            "opening_range", "M5", data.assets, data.fields, ParamGrid(PARAMS)
        )
        return engine
