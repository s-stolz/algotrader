import pandas as pd
import numpy as np
import logging

class CURRENCY_STRENGTH:
    @staticmethod
    def info() -> dict:
        return {
            'name': 'Currency Strength',
            'overlay': False,
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

    @staticmethod
    def run(data: pd.DataFrame) -> pd.DataFrame:
        data = data['close']

        def get_val(prev_val, curr_val):
            return (curr_val - prev_val) / ((curr_val + prev_val) / 2) * 10000

        def get_val_m(prev_val1, curr_val1, prev_val2, curr_val2):
            return get_val(prev_val1 * prev_val2, curr_val1 * curr_val2)

        def get_val_d(prev_val1, curr_val1, prev_val2, curr_val2):
            return get_val(prev_val1 / prev_val2, curr_val1 / curr_val2)

        shifted_data = data.shift(1)

        eurusd_val = get_val(shifted_data['EURUSD'], data['EURUSD'])
        gbpusd_val = get_val(shifted_data['GBPUSD'], data['GBPUSD'])
        usdjpy_val = get_val(shifted_data['USDJPY'], data['USDJPY'])
        audusd_val = get_val(shifted_data['AUDUSD'], data['AUDUSD'])
        nzdusd_val = get_val(shifted_data['NZDUSD'], data['NZDUSD'])
        usdcad_val = get_val(shifted_data['USDCAD'], data['USDCAD'])
        usdchf_val = get_val(shifted_data['USDCHF'], data['USDCHF'])
        
        # Derived pairs
        eurgbp_val = get_val_d(data['EURUSD'], shifted_data['EURUSD'], data['GBPUSD'], shifted_data['GBPUSD'])
        eurjpy_val = get_val_m(data['EURUSD'], shifted_data['EURUSD'], data['USDJPY'], shifted_data['USDJPY'])
        euraud_val = get_val_d(data['EURUSD'], shifted_data['EURUSD'], data['AUDUSD'], shifted_data['AUDUSD'])
        eurnzd_val = get_val_d(data['EURUSD'], shifted_data['EURUSD'], data['NZDUSD'], shifted_data['NZDUSD'])
        eurcad_val = get_val_d(data['EURUSD'], shifted_data['EURUSD'], data['USDCAD'], shifted_data['USDCAD'])
        eurchf_val = get_val_m(data['EURUSD'], shifted_data['EURUSD'], data['USDCHF'], shifted_data['USDCHF'])
        
        gbpjpy_val = get_val_m(data['GBPUSD'], shifted_data['GBPUSD'], data['USDJPY'], shifted_data['USDJPY'])
        gbpaud_val = get_val_m(data['GBPUSD'], shifted_data['GBPUSD'], data['AUDUSD'], shifted_data['AUDUSD'])
        gbpnzd_val = get_val_m(data['GBPUSD'], shifted_data['GBPUSD'], data['NZDUSD'], shifted_data['NZDUSD'])
        gbpcad_val = get_val_m(data['GBPUSD'], shifted_data['GBPUSD'], data['USDCAD'], shifted_data['USDCAD'])
        gbpchf_val = get_val_m(data['GBPUSD'], shifted_data['GBPUSD'], data['USDCHF'], shifted_data['USDCHF'])
        
        jpyaud_val = get_val_d(data['USDJPY'], shifted_data['USDJPY'], data['AUDUSD'], shifted_data['AUDUSD'])
        jpynzd_val = get_val_d(data['USDJPY'], shifted_data['USDJPY'], data['NZDUSD'], shifted_data['NZDUSD'])
        jpycad_val = get_val_d(data['USDJPY'], shifted_data['USDJPY'], data['USDCAD'], shifted_data['USDCAD'])
        jpychf_val = get_val_d(data['USDJPY'], shifted_data['USDJPY'], data['USDCHF'], shifted_data['USDCHF'])
        
        audnzd_val = get_val_m(data['AUDUSD'], shifted_data['AUDUSD'], data['NZDUSD'], shifted_data['NZDUSD'])
        audcad_val = get_val_m(data['AUDUSD'], shifted_data['AUDUSD'], data['USDCAD'], shifted_data['USDCAD'])
        audchf_val = get_val_m(data['AUDUSD'], shifted_data['AUDUSD'], data['USDCHF'], shifted_data['USDCHF'])
        
        nzdcad_val = get_val_m(data['NZDUSD'], shifted_data['NZDUSD'], data['USDCAD'], shifted_data['USDCAD'])
        nzdchf_val = get_val_m(data['NZDUSD'], shifted_data['NZDUSD'], data['USDCHF'], shifted_data['USDCHF'])
        
        cadchf_val = get_val_m(data['USDCAD'], shifted_data['USDCAD'], data['USDCHF'], shifted_data['USDCHF'])
        
        # Calculating the strength of each currency by averaging the values of its pairs
        strength = pd.DataFrame(index=data.index)
        strength['EUR'] = (eurusd_val + eurgbp_val + eurjpy_val + euraud_val + eurnzd_val + eurcad_val + eurchf_val) / 7
        strength['GBP'] = (gbpusd_val + eurgbp_val + gbpjpy_val + gbpaud_val + gbpnzd_val + gbpcad_val + gbpchf_val) / 7
        strength['JPY'] = (usdjpy_val + eurjpy_val + gbpjpy_val + jpyaud_val + jpynzd_val + jpycad_val + jpychf_val) / 7
        strength['AUD'] = (audusd_val + euraud_val + gbpaud_val + jpyaud_val + audnzd_val + audcad_val + audchf_val) / 7
        strength['NZD'] = (nzdusd_val + eurnzd_val + gbpnzd_val + jpynzd_val + audnzd_val + nzdcad_val + nzdchf_val) / 7
        strength['CAD'] = (usdcad_val + eurcad_val + gbpcad_val + jpycad_val + audcad_val + nzdcad_val + cadchf_val) / 7
        strength['CHF'] = (usdchf_val + eurchf_val + gbpchf_val + jpychf_val + audchf_val + nzdchf_val + cadchf_val) / 7
        strength['USD'] = (-eurusd_val - gbpusd_val + usdjpy_val - audusd_val - nzdusd_val + usdcad_val + usdchf_val) / 7
        # Detect new days
        new_day_mask = data.index.to_series().dt.date != data.index.to_series().dt.date.shift()
        new_day_indices = np.where(new_day_mask)[0]

        # Split the data into days
        split_strength = {col: [strength[col].iloc[start:end] for start, end in zip(new_day_indices, new_day_indices[1:])] + [strength[col].iloc[new_day_indices[-1]:]] for col in strength.columns}

        # Cumsum each day separately and recombine
        for col in split_strength:
            split_strength[col] = [np.cumsum(day) for day in split_strength[col]]
            split_strength[col] = np.concatenate(split_strength[col])

        strength = pd.DataFrame(split_strength, index=data.index)
        
        return strength