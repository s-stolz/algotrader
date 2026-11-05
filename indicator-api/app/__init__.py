from copy import deepcopy

from indicator_engine import get_batch_engine, get_registry
from indicator_engine.builtin_catalog import BUILTIN_CATALOG

INDICATOR_CATALOG = BUILTIN_CATALOG

ENGINE_REGISTRY = get_registry()
BATCH_ENGINE = get_batch_engine(ENGINE_REGISTRY)


def get_available_indicators() -> list[dict]:
    specs = ENGINE_REGISTRY.list_specs()
    return [
        {
            "id": registration.public_id,
            "indicator_id": registration.engine_id,
            "name": specs[registration.engine_id].name,
        }
        for registration in INDICATOR_CATALOG
    ]


def get_indicator_metadata(indicator_id: int) -> dict:
    registration = INDICATOR_CATALOG.get(indicator_id)
    engine_id = registration.engine_id
    spec = ENGINE_REGISTRY.get(engine_id).spec

    outputs = {name: {} for name in spec.outputs}
    outputs.update(deepcopy(registration.outputs))

    return {
        "id": indicator_id,
        "indicator_id": engine_id,
        "name": spec.name,
        "overlay": registration.overlay,
        "supports_live": registration.supports_live,
        "outputs": outputs,
        "parameters": spec.parameters,
        "inputs": spec.required_assets or [],
    }


def get_engine_id(indicator_id: int) -> str:
    return INDICATOR_CATALOG.get(indicator_id).engine_id


def supports_live(indicator_id: int) -> bool:
    return INDICATOR_CATALOG.get(indicator_id).supports_live
