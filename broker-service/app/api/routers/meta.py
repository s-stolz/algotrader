from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_container
from app.infrastructure.config import ServiceContainer

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/health")
async def health(container: ServiceContainer = Depends(get_container)) -> dict[str, object]:
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

    components["tokenLifecycle"] = container.token_lifecycle_component

    overall = "up" if all(c["status"] == "up" for c in components.values()) else "degraded"
    return {"status": overall, "components": components}
