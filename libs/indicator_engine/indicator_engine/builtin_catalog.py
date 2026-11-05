"""Assemble built-in application registrations in stable public catalog order."""

from .catalog import IndicatorCatalog
from .indicators.bbands import BBANDS_REGISTRATION
from .indicators.currency_strength import CURRENCY_STRENGTH_REGISTRATION
from .indicators.ema import EMA_REGISTRATION
from .indicators.macd import MACD_REGISTRATION
from .indicators.opening_range import OPENING_RANGE_REGISTRATION
from .indicators.rsi import RSI_REGISTRATION
from .indicators.sma import SMA_REGISTRATION

BUILTIN_CATALOG = IndicatorCatalog(
    [
        SMA_REGISTRATION,
        RSI_REGISTRATION,
        BBANDS_REGISTRATION,
        MACD_REGISTRATION,
        CURRENCY_STRENGTH_REGISTRATION,
        EMA_REGISTRATION,
        OPENING_RANGE_REGISTRATION,
    ]
)
