from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

from app.infrastructure.ctrader_oauth_client import CtraderOAuthClient
from app.infrastructure.token_repository import CtraderTokenState, RedisTokenRepository
from app.settings import CtraderCredentials, Settings

logger = logging.getLogger(__name__)


class TokenLifecycleManager:
    def __init__(
        self,
        settings: Settings,
        credentials: CtraderCredentials,
        repository: RedisTokenRepository,
        oauth_client: CtraderOAuthClient,
    ) -> None:
        self._settings = settings
        self._credentials = credentials
        self._repository = repository
        self._oauth_client = oauth_client
        self._lock = asyncio.Lock()
        self._refresh_task: asyncio.Task[None] | None = None
        self._running = False
        self._token_state: CtraderTokenState | None = None
        self._source = "unknown"
        self._last_refresh_error: str | None = None
        self._last_refresh_at: int | None = None
        self._token_refreshed_callback: Callable[[], Awaitable[None]] | None = None

    def set_token_refreshed_callback(
        self,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        self._token_refreshed_callback = callback

    async def startup(self) -> None:
        async with self._lock:
            self._running = True
            state = await self._repository.get_current_token()
            if state is None:
                now = int(time.time())
                state = CtraderTokenState(
                    access_token=self._credentials.access_token,
                    refresh_token=self._credentials.refresh_token,
                    expires_at=now + self._credentials.access_token_expires_in_seconds,
                    issued_at=now,
                )
                await self._repository.set_current_token(state)
                self._source = "env"
            else:
                self._source = "redis"

            self._token_state = state
            logger.info(
                "Initialized token lifecycle from %s (expires_at=%s)",
                self._source,
                state.expires_at,
            )

            if self._needs_refresh_now(state):
                await self._refresh_with_retries()
            self._schedule_next_refresh()

    async def shutdown(self) -> None:
        async with self._lock:
            self._running = False
            if self._refresh_task:
                self._refresh_task.cancel()
                self._refresh_task = None

    def get_access_token(self) -> str:
        if self._token_state is None:
            raise RuntimeError("Token lifecycle manager is not initialized")
        return self._token_state.access_token

    def health_component(self) -> dict[str, str | None]:
        state = self._token_state
        if state is None:
            return {"status": "down", "detail": "token state not initialized"}

        now = int(time.time())
        next_refresh_at = state.expires_at - self._settings.broker_token_refresh_early_seconds
        detail = (
            f"source={self._source} expires_at={state.expires_at} "
            f"next_refresh_at={next_refresh_at} "
            f"seconds_until_expiry={max(0, state.expires_at - now)}"
        )
        if self._last_refresh_at is not None:
            detail = f"{detail} last_refresh_at={self._last_refresh_at}"
        if self._last_refresh_error:
            detail = f"{detail} last_error={self._last_refresh_error}"
            return {"status": "degraded", "detail": detail}
        return {"status": "up", "detail": detail}

    def _needs_refresh_now(self, state: CtraderTokenState) -> bool:
        refresh_at = state.expires_at - self._settings.broker_token_refresh_early_seconds
        return refresh_at <= int(time.time())

    def _seconds_until_refresh(self, state: CtraderTokenState) -> float:
        refresh_at = state.expires_at - self._settings.broker_token_refresh_early_seconds
        return max(0.0, float(refresh_at - int(time.time())))

    def _schedule_next_refresh(self) -> None:
        if not self._running or self._token_state is None:
            return
        delay = self._seconds_until_refresh(self._token_state)
        self._schedule_refresh_in(delay)

    def _schedule_refresh_in(self, delay: float) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
        logger.info("Scheduling next token refresh in %.2f seconds", delay)
        self._refresh_task = asyncio.create_task(self._run_scheduled_refresh(delay))

    async def _run_scheduled_refresh(self, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            async with self._lock:
                if not self._running:
                    return
                await self._refresh_with_retries()
                self._schedule_next_refresh()
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Scheduled token refresh task failed")
            async with self._lock:
                if self._running:
                    retry_delay = float(
                        max(1, self._settings.broker_token_refresh_retry_delay_seconds)
                    )
                    self._schedule_refresh_in(retry_delay)

    async def _refresh_with_retries(self) -> None:
        if self._token_state is None:
            raise RuntimeError("Token state missing during refresh")

        attempts = max(0, self._settings.broker_token_refresh_max_retries)
        delay_seconds = max(1, self._settings.broker_token_refresh_retry_delay_seconds)
        for attempt in range(attempts + 1):
            try:
                result = await self._oauth_client.refresh_access_token(
                    self._token_state.refresh_token
                )
                self._token_state = CtraderTokenState(
                    access_token=result.access_token,
                    refresh_token=result.refresh_token,
                    issued_at=result.issued_at,
                    expires_at=result.issued_at + result.expires_in,
                )
                await self._repository.set_current_token(self._token_state)
                self._source = "refresh"
                self._last_refresh_error = None
                self._last_refresh_at = int(time.time())
                if self._token_refreshed_callback is not None:
                    await self._token_refreshed_callback()
                logger.info(
                    "Successfully refreshed cTrader access token (expires_at=%s)",
                    self._token_state.expires_at,
                )
                return
            except Exception as exc:
                self._last_refresh_error = str(exc)
                logger.exception(
                    "Failed to refresh cTrader token (attempt=%s/%s)",
                    attempt + 1,
                    attempts + 1,
                )
                if attempt >= attempts:
                    raise
                await asyncio.sleep(delay_seconds)
