import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from signals import signal as Signal
import pandas as pd
import pandas.testing as pdt


class TestSignals(unittest.TestCase):
    def setUp(self) -> None:
        # DataFrame for normal crossover case
        d1 = {'source1': [0, 1, 4, 8], 'source2': [1, 2, 3, 4]}
        self.df_cross = pd.DataFrame(data=d1)
        self.df_cross.columns = pd.MultiIndex.from_product([self.df_cross.columns, ['Symbol1']])

        # DataFrame for no crossover case
        d2 = {'source1': [0, 1, 2, 3], 'source2': [4, 5, 6, 7]}
        self.df_no_cross = pd.DataFrame(data=d2)
        self.df_no_cross.columns = pd.MultiIndex.from_product([self.df_no_cross.columns, ['Symbol1']])

        # DataFrame with NaN values
        d3 = {'source1': [0, 2, 4, 8], 'source2': [None, None, 3, 4]}
        self.df_with_nan = pd.DataFrame(data=d3)
        self.df_with_nan.columns = pd.MultiIndex.from_product([self.df_with_nan.columns, ['Symbol1']])

        # DataFrame with NaN values 2
        d4 = {'source1': [8, 4, 2, 1], 'source2': [None, None, 3, 4]}
        self.df_with_nan2 = pd.DataFrame(data=d4)
        self.df_with_nan2.columns = pd.MultiIndex.from_product([self.df_with_nan2.columns, ['Symbol1']])

    '''
    TESTS crossover
    '''
    def test_crossover(self):
        crossovers = Signal.crossover(self.df_cross['source1'], self.df_cross['source2'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, True, False]})
        
        pdt.assert_frame_equal(crossovers, expected_df, check_dtype=False, obj='crossover DataFrame')

    def test_no_crossover1(self):
        crossovers = Signal.crossover(self.df_no_cross['source1'], self.df_no_cross['source2'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, False, False]})
        
        pdt.assert_frame_equal(crossovers, expected_df, check_dtype=False, obj='no crossover DataFrame')

    def test_no_crossover2(self):
        crossovers = Signal.crossover(self.df_no_cross['source2'], self.df_no_cross['source1'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, False, False]})
        
        pdt.assert_frame_equal(crossovers, expected_df, check_dtype=False, obj='no crossover DataFrame')

    def test_crossover_with_nan(self):
        crossovers = Signal.crossover(self.df_with_nan['source1'], self.df_with_nan['source2'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, False, False]})
        
        pdt.assert_frame_equal(crossovers, expected_df, check_dtype=False, obj='crossover with NaN DataFrame')

    def test_crossover_with_nan2(self):
        crossovers = Signal.crossover(self.df_with_nan2['source2'], self.df_with_nan2['source1'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, False, False]})
        
        pdt.assert_frame_equal(crossovers, expected_df, check_dtype=False, obj='crossover with NaN DataFrame')

    '''
    TESTS crossunder
    '''
    def test_crossunder(self):
        crossunders = Signal.crossunder(self.df_cross['source2'], self.df_cross['source1'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, True, False]})

        pdt.assert_frame_equal(crossunders, expected_df, check_dtype=False, obj='crossunder DataFrame')

    def test_no_crossunder1(self):
        crossunders = Signal.crossover(self.df_no_cross['source1'], self.df_no_cross['source2'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, False, False]})
        
        pdt.assert_frame_equal(crossunders, expected_df, check_dtype=False, obj='no crossunder DataFrame')
    
    def test_no_crossunder2(self):
        crossunders = Signal.crossover(self.df_no_cross['source2'], self.df_no_cross['source1'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, False, False]})
        
        pdt.assert_frame_equal(crossunders, expected_df, check_dtype=False, obj='no crossunder DataFrame')

    def test_crossunder_with_nan(self):
        crossunders = Signal.crossunder(self.df_with_nan['source2'], self.df_with_nan['source1'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, False, False]})
        
        pdt.assert_frame_equal(crossunders, expected_df, check_dtype=False, obj='crossunder with NaN DataFrame')

    def test_crossunder_with_nan2(self):
        crossunders = Signal.crossunder(self.df_with_nan2['source1'], self.df_with_nan2['source2'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, False, False]})
        
        pdt.assert_frame_equal(crossunders, expected_df, check_dtype=False, obj='crossunder with NaN DataFrame')

    '''
    TESTS above
    '''
    def test_above(self):
        aboves = Signal.above(self.df_cross['source1'], self.df_cross['source2'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, True, True]})

        pdt.assert_frame_equal(aboves, expected_df, check_dtype=False)

    def test_above_with_nan(self):
        aboves = Signal.above(self.df_with_nan['source1'], self.df_with_nan['source2'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, True, True]})

        pdt.assert_frame_equal(aboves, expected_df, check_dtype=False)

    '''
    TEST below
    '''
    def test_below(self):
        belows = Signal.below(self.df_cross['source1'], self.df_cross['source2'])
        expected_df = pd.DataFrame(data={'Symbol1': [True, True, False, False]})

        pdt.assert_frame_equal(belows, expected_df, check_dtype=False)

    def test_below_with_nan(self):
        belows = Signal.below(self.df_with_nan2['source1'], self.df_with_nan2['source2'])
        expected_df = pd.DataFrame(data={'Symbol1': [False, False, True, True]})

        pdt.assert_frame_equal(belows, expected_df, check_dtype=False)   

if __name__ == '__main__':
    unittest.main()
