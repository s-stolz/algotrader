"""Stage observations stay local and cannot move an execution backwards."""

import unittest

from domain.progress import observe_progress, report_progress


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
