import pandas as pd
import numpy as np

from app.markets import get_symbol_mapping
from app.candles import get_candles_sync


METADATA: dict = {
    'name': 'Currency Strength',
    'overlay': False,
    'warmup': 2,
    'inputs': ['EURUSD', 'USDJPY', 'USDCHF', 'GBPUSD', 'AUDUSD', 'USDCAD', 'NZDUSD'],
    'outputs': {
        'EUR': {
            'type': 'line',
            'plotOptions': {
                'lineWidth': 2,
                'color': '#FF5252'
            },
        },
        'GBP': {
            'type': 'line',
            'plotOptions': {
                'lineWidth': 2,
                'color': '#4CAF50'
            },
        },
        'JPY': {
            'type': 'line',
            'plotOptions': {
                'lineWidth': 2,
                'color': '#00BCD4'
            },
        },
        'AUD': {
            'type': 'line',
            'plotOptions': {
                'lineWidth': 2,
                'color': '#2962ff'
            },
        },
        'NZD': {
            'type': 'line',
            'plotOptions': {
                'lineWidth': 2,
                'color': '#E040FB'
            },
        },
        'CAD': {
            'type': 'line',
            'plotOptions': {
                'lineWidth': 2,
                'color': '#9C27B0'
            },
        },
        'CHF': {
            'type': 'line',
            'plotOptions': {
                'lineWidth': 2,
                'color': '#880E4F'
            },
        },
        'USD': {
            'type': 'line',
            'plotOptions': {
                'lineWidth': 2,
                'color': '#FF9800'
            },
        }
    },
    'parameters': {
    }
}


class CURRENCY_STRENGTH:
    @staticmethod
    def run(data: pd.DataFrame, timeframe: int, start_date: str, end_date: str, limit: int) -> pd.DataFrame:
        symbol_ids_mapping = get_symbol_mapping(METADATA['inputs'])

        _data = get_candles_sync(symbol_ids_mapping, timeframe, start_date, end_date, limit)
        _data = _data['close'].dropna()

        def get_val(prev_val, curr_val):
            return (curr_val - prev_val) / ((curr_val + prev_val) / 2) * 10000

        def get_val_m(prev_val1, curr_val1, prev_val2, curr_val2):
            return get_val(prev_val1 * prev_val2, curr_val1 * curr_val2)

        def get_val_d(prev_val1, curr_val1, prev_val2, curr_val2):
            return get_val(prev_val1 / prev_val2, curr_val1 / curr_val2)

        shifted_data = _data.shift(1)

        eurusd_val = get_val(shifted_data['EURUSD'], _data['EURUSD'])
        gbpusd_val = get_val(shifted_data['GBPUSD'], _data['GBPUSD'])
        usdjpy_val = get_val(shifted_data['USDJPY'], _data['USDJPY'])
        audusd_val = get_val(shifted_data['AUDUSD'], _data['AUDUSD'])
        nzdusd_val = get_val(shifted_data['NZDUSD'], _data['NZDUSD'])
        usdcad_val = get_val(shifted_data['USDCAD'], _data['USDCAD'])
        usdchf_val = get_val(shifted_data['USDCHF'], _data['USDCHF'])

        # Derived pairs
        eurgbp_val = get_val_d(
            _data['EURUSD'],
            shifted_data['EURUSD'],
            _data['GBPUSD'],
            shifted_data['GBPUSD'])
        eurjpy_val = get_val_m(
            _data['EURUSD'],
            shifted_data['EURUSD'],
            _data['USDJPY'],
            shifted_data['USDJPY'])
        euraud_val = get_val_d(
            _data['EURUSD'],
            shifted_data['EURUSD'],
            _data['AUDUSD'],
            shifted_data['AUDUSD'])
        eurnzd_val = get_val_d(
            _data['EURUSD'],
            shifted_data['EURUSD'],
            _data['NZDUSD'],
            shifted_data['NZDUSD'])
        eurcad_val = get_val_d(
            _data['EURUSD'],
            shifted_data['EURUSD'],
            _data['USDCAD'],
            shifted_data['USDCAD'])
        eurchf_val = get_val_m(
            _data['EURUSD'],
            shifted_data['EURUSD'],
            _data['USDCHF'],
            shifted_data['USDCHF'])

        gbpjpy_val = get_val_m(
            _data['GBPUSD'],
            shifted_data['GBPUSD'],
            _data['USDJPY'],
            shifted_data['USDJPY'])
        gbpaud_val = get_val_m(
            _data['GBPUSD'],
            shifted_data['GBPUSD'],
            _data['AUDUSD'],
            shifted_data['AUDUSD'])
        gbpnzd_val = get_val_m(
            _data['GBPUSD'],
            shifted_data['GBPUSD'],
            _data['NZDUSD'],
            shifted_data['NZDUSD'])
        gbpcad_val = get_val_m(
            _data['GBPUSD'],
            shifted_data['GBPUSD'],
            _data['USDCAD'],
            shifted_data['USDCAD'])
        gbpchf_val = get_val_m(
            _data['GBPUSD'],
            shifted_data['GBPUSD'],
            _data['USDCHF'],
            shifted_data['USDCHF'])

        jpyaud_val = get_val_d(
            _data['USDJPY'],
            shifted_data['USDJPY'],
            _data['AUDUSD'],
            shifted_data['AUDUSD'])
        jpynzd_val = get_val_d(
            _data['USDJPY'],
            shifted_data['USDJPY'],
            _data['NZDUSD'],
            shifted_data['NZDUSD'])
        jpycad_val = get_val_d(
            _data['USDJPY'],
            shifted_data['USDJPY'],
            _data['USDCAD'],
            shifted_data['USDCAD'])
        jpychf_val = get_val_d(
            _data['USDJPY'],
            shifted_data['USDJPY'],
            _data['USDCHF'],
            shifted_data['USDCHF'])

        audnzd_val = get_val_m(
            _data['AUDUSD'],
            shifted_data['AUDUSD'],
            _data['NZDUSD'],
            shifted_data['NZDUSD'])
        audcad_val = get_val_m(
            _data['AUDUSD'],
            shifted_data['AUDUSD'],
            _data['USDCAD'],
            shifted_data['USDCAD'])
        audchf_val = get_val_m(
            _data['AUDUSD'],
            shifted_data['AUDUSD'],
            _data['USDCHF'],
            shifted_data['USDCHF'])

        nzdcad_val = get_val_m(
            _data['NZDUSD'],
            shifted_data['NZDUSD'],
            _data['USDCAD'],
            shifted_data['USDCAD'])
        nzdchf_val = get_val_m(
            _data['NZDUSD'],
            shifted_data['NZDUSD'],
            _data['USDCHF'],
            shifted_data['USDCHF'])

        cadchf_val = get_val_m(
            _data['USDCAD'],
            shifted_data['USDCAD'],
            _data['USDCHF'],
            shifted_data['USDCHF'])

        # Calculating the strength of each currency by averaging the values of its pairs
        strength = pd.DataFrame(index=_data.index)
        strength['EUR'] = (
            eurusd_val + eurgbp_val + eurjpy_val + euraud_val + eurnzd_val + eurcad_val + eurchf_val) / 7
        strength['GBP'] = (
            gbpusd_val + eurgbp_val + gbpjpy_val + gbpaud_val + gbpnzd_val + gbpcad_val + gbpchf_val) / 7
        strength['JPY'] = (
            usdjpy_val + eurjpy_val + gbpjpy_val + jpyaud_val + jpynzd_val + jpycad_val + jpychf_val) / 7
        strength['AUD'] = (
            audusd_val + euraud_val + gbpaud_val + jpyaud_val + audnzd_val + audcad_val + audchf_val) / 7
        strength['NZD'] = (
            nzdusd_val + eurnzd_val + gbpnzd_val + jpynzd_val + audnzd_val + nzdcad_val + nzdchf_val) / 7
        strength['CAD'] = (
            usdcad_val + eurcad_val + gbpcad_val + jpycad_val + audcad_val + nzdcad_val + cadchf_val) / 7
        strength['CHF'] = (
            usdchf_val + eurchf_val + gbpchf_val + jpychf_val + audchf_val + nzdchf_val + cadchf_val) / 7
        strength['USD'] = (-eurusd_val - gbpusd_val + usdjpy_val -
                           audusd_val - nzdusd_val + usdcad_val + usdchf_val) / 7

        date_key = strength.index.to_series().dt.date
        strength = strength.groupby(date_key, group_keys=False).cumsum()

        return strength
