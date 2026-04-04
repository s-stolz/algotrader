import unittest

import numpy as np
from indicator_engine.core.bars import BarBuffer
from indicator_engine.core.history import HistoryPolicy


class BarBufferTests(unittest.TestCase):
    def test_rolling_buffer_evicts_oldest_rows(self) -> None:
        buffer = BarBuffer(
            assets=["EURUSD"],
            fields=["close"],
            history=HistoryPolicy(mode="rolling", max_rows=2),
        )

        buffer.append(1000, np.array([[1.0]]))
        buffer.append(2000, np.array([[2.0]]))
        buffer.append(3000, np.array([[3.0]]))

        view = buffer.view()
        self.assertEqual(len(buffer), 2)
        self.assertEqual(buffer.earliest_timestamp(), 2000)
        self.assertEqual(buffer.latest_timestamp(), 3000)
        self.assertEqual(view.time.tolist(), [2000, 3000])
        self.assertEqual(view.data[:, 0, 0].tolist(), [2.0, 3.0])


if __name__ == "__main__":
    unittest.main()
