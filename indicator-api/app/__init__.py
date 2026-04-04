from indicator_engine import get_batch_engine, get_registry

from .ui_metadata import UI_METADATA

ENGINE_REGISTRY = get_registry()
BATCH_ENGINE = get_batch_engine(ENGINE_REGISTRY)

INDICATOR_MAP: dict[int, str] = {
    1: "sma",
    2: "rsi",
    3: "bbands",
    4: "macd",
    5: "currency_strength",
}


def get_available_indicators() -> list[dict]:
    return [
        {"id": indicator_id, "name": ENGINE_REGISTRY.get(engine_id).spec.name}
        for indicator_id, engine_id in INDICATOR_MAP.items()
    ]


def get_indicator_metadata(indicator_id: int) -> dict:
    engine_id = INDICATOR_MAP[indicator_id]
    spec = ENGINE_REGISTRY.get(engine_id).spec
    ui = UI_METADATA.get(engine_id, {})

    outputs = {name: {} for name in spec.outputs}
    outputs.update(ui.get("outputs", {}))

    return {
        "id": indicator_id,
        "indicator_id": engine_id,
        "name": spec.name,
        "overlay": ui.get("overlay", False),
        "outputs": outputs,
        "parameters": spec.parameters,
        "inputs": spec.required_assets or [],
    }


def get_engine_id(indicator_id: int) -> str:
    return INDICATOR_MAP[indicator_id]


def get_indicator_by_id(indicator_id: int):
    engine_id = INDICATOR_MAP[indicator_id]
    return ENGINE_REGISTRY.get(engine_id)
