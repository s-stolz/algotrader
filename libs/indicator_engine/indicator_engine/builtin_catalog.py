"""Built-in application indicators: add each implementation in exactly one entry."""

from .catalog import IndicatorCatalog, IndicatorRegistration
from .indicators.bbands import BBANDS
from .indicators.currency_strength import CurrencyStrength
from .indicators.ema import EMA
from .indicators.macd import MACD
from .indicators.opening_range import OpeningRange
from .indicators.rsi import RSI
from .indicators.sma import SMA

BUILTIN_CATALOG = IndicatorCatalog(
    [
        IndicatorRegistration(
            public_id=1,
            implementation=SMA,
            supports_live=True,
            overlay=True,
            outputs={"sma": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#FCFC4E"}}},
        ),
        IndicatorRegistration(
            public_id=2,
            implementation=RSI,
            supports_live=True,
            overlay=False,
            outputs={"rsi": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#7E57C2"}}},
        ),
        IndicatorRegistration(
            public_id=3,
            implementation=BBANDS,
            supports_live=True,
            overlay=True,
            outputs={
                "lower": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#089981"}},
                "mid": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#2962ff"}},
                "upper": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#f23645"}},
            },
        ),
        IndicatorRegistration(
            public_id=4,
            implementation=MACD,
            supports_live=True,
            overlay=False,
            outputs={
                "hist": {
                    "type": "histogram",
                    "plotOptions": {"color": "#089981", "priceFormat": {"minMove": 1e-05}},
                },
                "macd": {
                    "type": "line",
                    "plotOptions": {
                        "lineWidth": 2,
                        "color": "#2962ff",
                        "priceFormat": {"minMove": 1e-05},
                    },
                },
                "signal": {
                    "type": "line",
                    "plotOptions": {
                        "lineWidth": 2,
                        "color": "#f23645",
                        "priceFormat": {"minMove": 1e-05},
                    },
                },
            },
        ),
        IndicatorRegistration(
            public_id=5,
            implementation=CurrencyStrength,
            supports_live=False,
            overlay=False,
            outputs={
                "EUR": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#FF5252"}},
                "GBP": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#4CAF50"}},
                "JPY": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#00BCD4"}},
                "AUD": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#2962ff"}},
                "NZD": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#E040FB"}},
                "CAD": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#9C27B0"}},
                "CHF": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#880E4F"}},
                "USD": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#FF9800"}},
            },
        ),
        IndicatorRegistration(
            public_id=6,
            implementation=EMA,
            supports_live=True,
            overlay=True,
            outputs={"ema": {"type": "line", "plotOptions": {"lineWidth": 2, "color": "#2962ff"}}},
        ),
        IndicatorRegistration(
            public_id=7,
            implementation=OpeningRange,
            supports_live=False,
            overlay=True,
            outputs={
                "range_high": {
                    "type": "opening_range",
                    "label": "Range",
                    "plotOptions": {
                        "color": "#2962ff",
                        "fillColor": "rgba(41, 98, 255, 0.12)",
                        "lineWidth": 1,
                        "showExtensions": True,
                    },
                }
            },
        ),
    ]
)
