import pandas as pd
import pandas as _pd  # alias for internal date handling without shadowing
from datetime import timedelta
from typing import Any


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def estimate_warmup(metadata: dict, params: dict) -> int:
    """Estimate indicator warmup (lookback) using per-indicator metadata.

    Supported metadata keys (all optional):
      - warmup (int): explicit override.
      - warmup_params (list[str]): parameter names to consider.
      - warmup_mode ("max" | "sum"): how to combine warmup_params values (default: max).
      - warmup_buffer (int): extra bars to add (default: 2).

    Fallbacks:
      - If no hints and no explicit warmup: return 1.
    """
    explicit_val = metadata.get('warmup')
    if _is_int(explicit_val):
        return int(explicit_val)  # type: ignore[arg-type]

    warmup_params = metadata.get('warmup_params', [])
    if not isinstance(warmup_params, list):  # guard
        warmup_params = []
    mode = metadata.get('warmup_mode', 'max')
    buffer = metadata.get('warmup_buffer', 0)
    numeric_values: list[int] = []
    for name in warmup_params:
        val = params.get(name)
        if _is_int(val):
            numeric_values.append(int(val))  # type: ignore[arg-type]

    if not numeric_values:
        return 1

    if mode == 'sum':
        base = sum(numeric_values)
    else:  # default max
        base = max(numeric_values)

    return max(1, base + (buffer if _is_int(buffer) else 0))


def prepare_parameters(
        indicator_info: dict, custom_parameters: dict, symbol_id: int, timeframe: int,
        start_date: str | None, end_date: str | None, limit: int | None) -> dict:
    """Prepare parameters for the indicator."""
    parameters = {}

    for param_name, param_details in indicator_info['parameters'].items():
        param_default = param_details.get('default')
        parameters[param_name] = custom_parameters.get(
            param_name, param_default)

    parameters['symbol_id'] = symbol_id
    parameters['timeframe'] = parameters['timeframe'] if 'timeframe' in parameters else timeframe
    parameters['limit'] = limit
    parameters['start_date'] = start_date
    parameters['end_date'] = end_date

    return parameters


def format_indicator_response(
        indicator_data: pd.DataFrame, indicator_id: int, metadata: dict) -> dict:
    # Format the response
    indicator_reset = indicator_data.reset_index()
    indicator_reset['timestamp'] = indicator_reset['timestamp'].dt.strftime(
        '%Y-%m-%d %H:%M:%SZ')

    # response_data = {
    #     'data': {
    #         'id': indicator_id,
    #         'indicator_info': metadata,
    #         'indicator_data': indicator_reset.to_dict(orient='records')
    #     }
    # }
    return {'data': indicator_reset.to_dict(orient='records')}


def adjust_fetch_bounds(
    *,
    start_date: str | None,
    limit: int | None,
    timeframe: int,
    warmup: int,
) -> tuple[str | None, int | None, str | None, int | None]:
    """Compute adjusted (earlier/larger) fetch parameters and preserve originals.

    Returns (fetch_start_date, fetch_limit, original_start_date, original_limit).

    If start_date is provided we back off by warmup * timeframe minutes.
    If only limit is provided we expand the limit by warmup.
    If both provided, both adjustments are applied.
    """
    orig_start = start_date
    orig_limit = limit

    fetch_start = start_date
    fetch_limit = limit

    if start_date:
        try:
            dt = _pd.to_datetime(start_date, utc=True)
            fetch_start = (dt - timedelta(minutes=timeframe * (warmup - 1))
                           ).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            # If parsing fails, leave start_date unchanged
            pass

    if limit is not None:
        fetch_limit = limit + (warmup - 1)

    return fetch_start, fetch_limit, orig_start, orig_limit


def trim_indicator_output(
    df: pd.DataFrame,
    *,
    original_start_date: str | None,
    original_limit: int | None,
) -> pd.DataFrame:
    """Trim indicator DataFrame to honor original user constraints after warmup.

    - Drop initial NaNs.
    - Enforce start_date (if given) after dropping NaNs.
    - Enforce limit (tail) if provided.
    """
    if df is None or df.empty:
        return df

    out = df.dropna(how='any')
    if original_start_date:
        try:
            dt = _pd.to_datetime(original_start_date, utc=True)
            out = out[out.index >= dt]
        except Exception:
            pass

    if original_limit is not None:
        out = out.tail(original_limit)

    return out
