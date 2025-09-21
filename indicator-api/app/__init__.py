from .indicators.sma import SMA
from .indicators.sma import METADATA as SMA_METADATA
from .indicators.rsi import RSI
from .indicators.rsi import METADATA as RSI_METADATA
from .indicators.bbands import BBANDS
from .indicators.bbands import METADATA as BBANDS_METADATA
from .indicators.macd import MACD
from .indicators.macd import METADATA as MACD_METADATA
from .indicators.currencyStrength import CURRENCY_STRENGTH
from .indicators.currencyStrength import METADATA as CURRENCY_STRENGTH_METADATA

INDICATORS = {
    1: {
        'metadata': SMA_METADATA,
        'class': SMA
    },
    2: {
        'metadata': RSI_METADATA,
        'class': RSI
    },
    3: {
        'metadata': BBANDS_METADATA,
        'class': BBANDS
    },
    4: {
        'metadata': MACD_METADATA,
        'class': MACD
    },
    5: {
        'metadata': CURRENCY_STRENGTH_METADATA,
        'class': CURRENCY_STRENGTH
    }
}


def get_available_indicators() -> list[dict]:
    """Returns a list of all available indicators with their metadata."""
    return [
        {
            'id': indicator_id,
            'name':  indicator['metadata']['name'],
        }
        for indicator_id, indicator in INDICATORS.items()
    ]


def get_indicator_metadata(indicator_id: int) -> dict:
    """
    Returns the metadata of the specified indicator by ID.

    Args:
        indicator_id (int): The ID of the indicator.

    Returns:
        dict: The metadata of the requested indicator.
    """
    return INDICATORS[indicator_id]['metadata']


def get_indicator_by_id(indicator_id: int, *args, **kwargs):
    """
    Returns an instance of the specified indicator by ID, initialized with any provided arguments.

    Args:
        indicator_id (int): The ID of the indicator.
        *args: Positional arguments for the indicator.
        **kwargs: Keyword arguments for the indicator.

    Returns:
        An instance of the requested indicator.
    """
    # if indicator_id not in INDICATORS:
    #     available_ids = [indicator['id'] for indicator in INDICATORS]
    #     raise ValueError(
    #         f"Indicator with ID '{indicator_id}' is not available. Available indicator IDs: {available_ids}")
    return INDICATORS[indicator_id]['class'](*args, **kwargs)
