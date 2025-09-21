from __future__ import annotations

from typing import Protocol, Any, Callable, Dict, Set
import inspect
import sys
import pandas as pd
from logger import logger


class Indicator(Protocol):
    """Protocol every indicator class should satisfy.

    Each indicator should expose a static ``run`` method with the first
    argument named ``data`` (a ``pd.DataFrame``) and subsequent keyword
    parameters for its configuration. Optional convenience:
    A module-level ``METADATA`` dict containing a ``parameters`` mapping
    with possible defaults (already used across the project).
    """

    @staticmethod
    def run(data: pd.DataFrame, **kwargs) -> pd.DataFrame: ...  # type: ignore[override]


def _load_metadata(indicator_cls: type) -> Dict[str, Any]:
    """Fetch the module-level METADATA dict for an indicator class if present."""
    module = sys.modules.get(indicator_cls.__module__)
    if not module:
        return {}
    return getattr(module, 'METADATA', {}) or {}


def execute_indicator(
    indicator: Any,
    data: pd.DataFrame = pd.DataFrame(),
    /,
    *,
    strict: bool = False,
    warn_extra: bool = True,
    allow_extra: bool = True,
    use_metadata_defaults: bool = True,
    fill_metadata_defaults_for_required: bool = True,
    **params: Any,
) -> pd.DataFrame:
    """Execute an indicator while filtering/validating parameters.

    Parameters
    ----------
    indicator : type | object
        The indicator class (e.g. ``SMA``) or an instance of it containing a static ``run`` method.
    data : pd.DataFrame
        Price / timeseries dataframe passed as first argument.
    strict : bool, default False
        If True, any unexpected / extra parameter raises instead of warning.
    warn_extra : bool, default True
        Emit a warning when extra parameters are ignored.
    allow_extra : bool, default True
        If False and extras are present, raise (overrides warn_extra).
    use_metadata_defaults : bool, default True
        Use defaults defined in the module-level ``METADATA['parameters']`` for
        parameters not explicitly passed by caller (without overriding function
        signature defaults; Python already handles those).
    fill_metadata_defaults_for_required : bool, default True
        When the ``run`` signature marks a parameter as required (no Python-level
        default) but a default exists in METADATA, automatically fill it.
    **params : Any
        Arbitrary superset of parameters coming from higher-level strategy code.

    Returns
    -------
    pd.DataFrame
        Indicator output from ``indicator_cls.run``.
    """

    # Support being passed either the class or an already-instantiated object
    indicator_cls = indicator if inspect.isclass(indicator) else indicator.__class__
    run_fn: Callable[..., pd.DataFrame] = getattr(indicator, 'run') if not inspect.isclass(
        indicator) else getattr(indicator_cls, 'run')
    sig = inspect.signature(run_fn)

    # Map of runtime arguments we will forward
    forwarded: Dict[str, Any] = {}
    used: Set[str] = set()

    metadata = _load_metadata(indicator_cls)
    meta_params: Dict[str, Any] = metadata.get(
        'parameters', {}) if isinstance(metadata, dict) else {}

    for name, param in sig.parameters.items():
        if name == 'data':
            continue
        if param.kind not in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
            continue  # Skip *args/**kwargs in signature if any appear

        if name in params:
            forwarded[name] = params[name]
            used.add(name)
            continue

        # Not provided explicitly
        has_py_default = param.default is not inspect._empty
        if not has_py_default:
            # Required param in signature
            meta_def_available = name in meta_params and 'default' in meta_params[name]
            if meta_def_available and fill_metadata_defaults_for_required:
                forwarded[name] = meta_params[name]['default']
                used.add(name)
            else:
                raise ValueError(
                    f"Missing required parameter '{name}' for indicator {indicator_cls.__name__}"  # noqa: E501
                )
        else:
            # Let Python apply its own default by omitting it
            if use_metadata_defaults and name in meta_params and name not in forwarded:
                # Only fill if user didn't supply and we maybe want to override? We choose NOT to
                # override the Python default here to keep function signature authoritative.
                pass

    extras = set(params.keys()) - used
    if extras:
        if strict or (not allow_extra):
            raise TypeError(
                f"Indicator {indicator_cls.__name__} received unexpected parameters: {sorted(extras)}"
            )
        elif warn_extra:
            logger.warning(
                f"[{indicator_cls.__name__}] Ignored extra parameters: {sorted(extras)}",
                stacklevel=2,
            )

    return run_fn(data=data, **forwarded)


__all__ = [
    'Indicator',
    'execute_indicator',
]
