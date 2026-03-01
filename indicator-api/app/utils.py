from typing import Any

import pandas as pd


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
        start_ms: int | None, end_ms: int | None, limit: int | None) -> dict:
    """Prepare parameters for the indicator."""
    parameters = {}

    for param_name, param_details in indicator_info['parameters'].items():
        param_default = param_details.get('default')
        parameters[param_name] = custom_parameters.get(
            param_name, param_default)

    parameters['symbol_id'] = symbol_id
    parameters['timeframe'] = parameters['timeframe'] if 'timeframe' in parameters else timeframe
    parameters['limit'] = limit
    parameters['start_ms'] = start_ms
    parameters['end_ms'] = end_ms

    return parameters


def format_indicator_response(
    indicator_data: pd.DataFrame,
    metadata: dict,
) -> dict:
    # Format timestamps as epoch milliseconds in UTC.
    indicator_reset = indicator_data.reset_index()
    indicator_reset['timestamp_ms'] = (
        indicator_reset['timestamp'].astype('int64') // 1_000_000
    )
    indicator_reset = indicator_reset.drop(columns=['timestamp'])

    response_data = {
        'data': {
            'indicator_info': metadata,
            'indicator_data': indicator_reset.to_dict(orient='records')
        }
    }
    return response_data


def adjust_fetch_bounds(
    *,
    start_ms: int | None,
    limit: int | None,
    timeframe: int,
    warmup: int,
) -> tuple[int | None, int | None, int | None, int | None]:
    """Compute adjusted (earlier/larger) fetch parameters and preserve originals.

    Returns (fetch_start_ms, fetch_limit, original_start_ms, original_limit).

    If start_ms is provided we back off by warmup * timeframe minutes.
    If only limit is provided we expand the limit by warmup.
    If both provided, both adjustments are applied.
    """
    orig_start = start_ms
    orig_limit = limit

    fetch_start = start_ms
    fetch_limit = limit

    if start_ms is not None:
        warmup_offset_ms = (warmup - 1) * timeframe * 60 * 1000
        fetch_start = max(0, start_ms - warmup_offset_ms)

    if limit is not None:
        fetch_limit = limit + (warmup - 1)

    return fetch_start, fetch_limit, orig_start, orig_limit


def trim_indicator_output(
    df: pd.DataFrame,
    *,
    original_start_ms: int | None,
    original_limit: int | None,
) -> pd.DataFrame:
    """Trim indicator DataFrame to honor original user constraints after warmup.

    - Drop initial NaNs.
    - Enforce start_ms (if given) after dropping NaNs.
    - Enforce limit (tail) if provided.
    """
    if df is None or df.empty:
        return df

    out = df.dropna(how='any')
    if original_start_ms is not None:
        out = out[out.index >= pd.to_datetime(original_start_ms, unit='ms', utc=True)]

    if original_limit is not None:
        out = out.tail(original_limit)

    return out
