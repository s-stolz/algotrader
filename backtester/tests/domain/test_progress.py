"""Stage observations stay local and cannot move an execution backwards."""

import unittest

from domain.progress import CandleProgress, observe_progress, report_progress


class ProgressTests(unittest.TestCase):
    def test_scope_restoration_monotonicity_and_no_observer(self):
        outer, inner = [], []
        report_progress("saving")
        with observe_progress(outer.append):
            report_progress("loading_data")
            with observe_progress(inner.append):
                report_progress("simulating")
                report_progress("loading_data")
                report_progress("simulating")
            report_progress("preparing_indicators")
        report_progress("saving")
        self.assertEqual(outer, ["loading_data", "preparing_indicators"])
        self.assertEqual(inner, ["simulating"])

    def test_candle_batches_final_remainder_and_early_exit(self):
        updates = []
        with observe_progress(
            lambda stage: None, lambda done, total: updates.append((done, total))
        ):
            progress = CandleProgress(4_003)
            for _ in range(2_017):
                progress.begin_candle()
            progress.report()
        self.assertEqual(updates, [(0, 4_003), (1_000, 4_003), (2_000, 4_003), (2_017, 4_003)])
        progress.report()
        self.assertEqual(len(updates), 4)
