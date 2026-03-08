from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from urllib import parse, request
from urllib.error import HTTPError, URLError

from app.settings import CtraderCredentials


@dataclass(frozen=True, slots=True)
class RefreshResult:
    access_token: str
    refresh_token: str
    expires_in: int
    issued_at: int


class CtraderOAuthClient:
    def __init__(self, credentials: CtraderCredentials) -> None:
        self._credentials = credentials

    async def refresh_access_token(self, refresh_token: str) -> RefreshResult:
        payload = await asyncio.to_thread(self._refresh_request, refresh_token)
        access_token = str(payload.get("access_token", "")).strip()
        if not access_token:
            raise RuntimeError("Refresh response missing access_token")

        next_refresh_token = str(payload.get("refresh_token", refresh_token)).strip()
        expires_in = payload.get(
            "expires_in",
            self._credentials.access_token_expires_in_seconds,
        )
        try:
            expires_in_seconds = max(1, int(expires_in))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Refresh response has invalid expires_in") from exc

        return RefreshResult(
            access_token=access_token,
            refresh_token=next_refresh_token,
            expires_in=expires_in_seconds,
            issued_at=int(time.time()),
        )

    def _refresh_request(self, refresh_token: str) -> dict:
        body = parse.urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self._credentials.client_id,
                "client_secret": self._credentials.secret,
            }
        ).encode("utf-8")
        req = request.Request(
            self._credentials.token_url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with request.urlopen(
                req,
                timeout=self._credentials.token_request_timeout_seconds,
            ) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8") if exc.fp else str(exc)
            raise RuntimeError(f"Token refresh failed ({exc.code}): {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Token refresh failed: {exc.reason}") from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Token refresh returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Token refresh returned non-object payload")
        return decoded
