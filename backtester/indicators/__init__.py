from .sma import SMA
from .rsi import RSI
from .bbands import BBANDS
from .macd import MACD

INDICATORS = {
    'Simple Moving Average': SMA,
    'Relative Strength Index': RSI,
    'Bollinger Bands': BBANDS,
    "Moving Average Convergence Divergence": MACD
}

def get_available_indicators() -> list[str]:
    """Returns a list of all available indicator names."""
    return list(INDICATORS.keys())

def get_indicator_instance(name: str, *args, **kwargs):
    """
    Returns an instance of the specified indicator, initialized with any provided arguments.

    Args:
        name (str): The name of the indicator.
        *args: Positional arguments for the indicator.
        **kwargs: Keyword arguments for the indicator.

    Returns:
        An instance of the requested indicator.
    """
    if name not in INDICATORS:
        raise ValueError(f"Indicator '{name}' is not available. Available indicators: {get_available_indicators()}")
    return INDICATORS[name](*args, **kwargs)
