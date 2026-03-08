from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class CtraderTokenState:
    access_token: str
    refresh_token: str
    expires_at: int
    issued_at: int


class RedisTokenRepository:
    def __init__(self, redis: "Redis", key: str) -> None:
        self._redis = redis
        self._key = key

    async def get_current_token(self) -> CtraderTokenState | None:
        payload = await self._redis.hgetall(self._key)
        if not payload:
            return None

        values = {self._decode(k): self._decode(v) for k, v in payload.items()}
        try:
            access_token = values["access_token"]
            refresh_token = values["refresh_token"]
            expires_at = int(values["expires_at"])
            issued_at = int(values["issued_at"])
        except (KeyError, ValueError) as exc:
            raise RuntimeError(f"Invalid token payload in Redis hash {self._key}") from exc

        return CtraderTokenState(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            issued_at=issued_at,
        )

    async def set_current_token(self, state: CtraderTokenState) -> None:
        mapping: dict[str, Any] = {
            "access_token": state.access_token,
            "refresh_token": state.refresh_token,
            "expires_at": str(state.expires_at),
            "issued_at": str(state.issued_at),
        }
        await self._redis.hset(self._key, mapping=mapping)

    @staticmethod
    def _decode(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)
