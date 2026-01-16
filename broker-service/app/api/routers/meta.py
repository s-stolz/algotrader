from fastapi import APIRouter, Depends

from app.api.dependencies import get_container
from app.api.schemas import HealthComponent, HealthResponse
from app.infrastructure.config import ServiceContainer

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/health", response_model=HealthResponse)
async def health(container: ServiceContainer = Depends(get_container)) -> HealthResponse:
    components: dict[str, HealthComponent] = {}

    ctrader_status = "up" if container.broker_connected else "starting"
    components["ctrader"] = HealthComponent(
        status=ctrader_status,
        detail="Authenticated" if container.broker_connected else "Awaiting authentication",
    )

    try:
        await container.redis.ping()  # type: ignore[func-returns-value]
        components["redis"] = HealthComponent(status="up")
    except Exception as exc:
        components["redis"] = HealthComponent(status="down", detail=str(exc))

    components["tickStreams"] = HealthComponent(
        status="up",
        detail=f"active={container.active_streams}",
    )

    components["trendbarStreams"] = HealthComponent(
        status="up",
        detail=f"active={container.active_trendbar_streams}",
    )

    overall = "up" if all(c.status == "up" for c in components.values()) else "degraded"
    return HealthResponse(status=overall, components=components)
