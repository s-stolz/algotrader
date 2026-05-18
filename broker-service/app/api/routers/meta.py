from __future__ import annotations

from typing import Any, Mapping, Protocol

from fastapi import APIRouter, Depends

from app.api.dependencies import get_container

router = APIRouter(prefix="/meta", tags=["meta"])


class HealthContainer(Protocol):
    @property
    def broker_connected(self) -> bool: ...

    @property
    def active_streams(self) -> int: ...

    @property
    def active_trendbar_streams(self) -> int: ...

    @property
    def redis(self) -> Any: ...

    @property
    def token_lifecycle_component(self) -> Mapping[str, str | None]: ...


@router.get("/health")
async def health(container: HealthContainer = Depends(get_container)) -> dict[str, Any]:
    components: dict[str, dict[str, str | None]] = {}

    ctrader_status = "up" if container.broker_connected else "starting"
    components["ctrader"] = {
        "status": ctrader_status,
        "detail": "Authenticated" if container.broker_connected else "Awaiting authentication",
    }

    try:
        await container.redis.ping()  # type: ignore[func-returns-value]
        components["redis"] = {"status": "up", "detail": None}
    except Exception as exc:
        components["redis"] = {"status": "down", "detail": str(exc)}

    components["tickStreams"] = {
        "status": "up",
        "detail": f"active={container.active_streams}",
    }

    components["trendbarStreams"] = {
        "status": "up",
        "detail": f"active={container.active_trendbar_streams}",
    }

    components["tokenLifecycle"] = dict(container.token_lifecycle_component)

    overall = "up" if all(c["status"] == "up" for c in components.values()) else "degraded"
    return {"status": overall, "components": components}
