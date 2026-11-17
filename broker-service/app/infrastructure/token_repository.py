from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CtraderTokenState:
    access_token: str
    refresh_token: str
    expires_at: int
    issued_at: int
    client_id: str = ""
    account_id: str = ""
    environment: str = ""


class RedisTokenRepository:
    def __init__(self, redis: Any, key: str) -> None:
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
            client_id=values.get("client_id", ""),
            account_id=values.get("account_id", ""),
            environment=values.get("environment", ""),
        )

    async def set_current_token(self, state: CtraderTokenState) -> None:
        await self._redis.hset(self._key, mapping=self._mapping(state))

    async def compare_and_set_current_token(
        self, previous: CtraderTokenState, state: CtraderTokenState
    ) -> bool:
        script = """
        if redis.call('HGET', KEYS[1], 'access_token') ~= ARGV[1]
            or redis.call('HGET', KEYS[1], 'refresh_token') ~= ARGV[2]
            or (redis.call('HGET', KEYS[1], 'client_id') or '') ~= ARGV[3]
            or (redis.call('HGET', KEYS[1], 'account_id') or '') ~= ARGV[4]
            or (redis.call('HGET', KEYS[1], 'environment') or '') ~= ARGV[5] then
            return 0
        end
        redis.call('HSET', KEYS[1], unpack(ARGV, 6))
        return 1
        """
        arguments = [
            previous.access_token,
            previous.refresh_token,
            previous.client_id,
            previous.account_id,
            previous.environment,
        ]
        for field, value in self._mapping(state).items():
            arguments.extend((field, value))
        if await self._redis.eval(script, 1, self._key, *arguments):
            return True
        # A prior write may have succeeded before its acknowledgement was lost.
        return await self.get_current_token() == state

    @staticmethod
    def _mapping(state: CtraderTokenState) -> dict[str, str]:
        return {
            "access_token": state.access_token,
            "refresh_token": state.refresh_token,
            "expires_at": str(state.expires_at),
            "issued_at": str(state.issued_at),
            "client_id": state.client_id,
            "account_id": state.account_id,
            "environment": state.environment,
        }

    @staticmethod
    def _decode(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)
