import os
from contextlib import asynccontextmanager

import uvicorn
from algotrader_logger import RequestLoggingMiddleware, configure_logging
from app.routes import indicators_router, live_indicator_streams_router, system_router
from app.services.candle_cache import CandleCache
from app.services.live_indicator_manager import LiveIndicatorManager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _load_log_level() -> str:
    return os.getenv("INDICATOR_API_LOG_LEVEL", "INFO")


def _load_log_format() -> str:
    return os.getenv("INDICATOR_API_LOG_FORMAT", "pretty")


configure_logging(
    service_name="indicator-api",
    level=_load_log_level(),
    format=_load_log_format(),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache_ttl = int(os.getenv("INDICATOR_HISTORY_CACHE_TTL_SECONDS", "180"))
    cache_entries = int(os.getenv("INDICATOR_HISTORY_CACHE_MAX_ENTRIES", "128"))
    app.state.candle_cache = CandleCache(ttl_seconds=cache_ttl, max_entries=cache_entries)
    app.state.live_indicator_manager = LiveIndicatorManager(app.state.candle_cache)
    try:
        yield
    finally:
        manager = getattr(app.state, "live_indicator_manager", None)
        if manager is not None:
            await manager.shutdown()


app = FastAPI(
    title="Indicator API",
    description="Indicator API for algotrader",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(system_router)
app.include_router(indicators_router)
app.include_router(live_indicator_streams_router)


if __name__ == "__main__":
    port = int(os.getenv("INDICATOR_API_PORT", 8010))
    host = os.getenv("INDICATOR_API_BIND_HOST", "0.0.0.0")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=["/app"],
        log_level=_load_log_level().lower(),
        log_config=None,
    )
