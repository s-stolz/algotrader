from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any
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
        return self._parse_result(payload, refresh_token)

    async def exchange_authorization_code(self, code: str, redirect_uri: str) -> RefreshResult:
        payload = await asyncio.to_thread(
            self._token_request,
            {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        )
        if "expiresIn" not in payload and "expires_in" not in payload:
            raise RuntimeError("Authorization response missing expires_in")
        return self._parse_result(payload, "")

    def _parse_result(self, payload: dict[str, Any], refresh_token: str) -> RefreshResult:
        if payload.get("errorCode"):
            code = str(payload["errorCode"])
            safe_code = code if re.fullmatch(r"[A-Z0-9_]{1,64}", code) else "UNKNOWN"
            raise RuntimeError(f"Token refresh failed (code {safe_code})")
        access_token = str(payload.get("accessToken", payload.get("access_token", ""))).strip()
        if not access_token:
            raise RuntimeError("Token response missing access_token")
        next_refresh_token = str(
            payload.get("refreshToken", payload.get("refresh_token", refresh_token))
        ).strip()
        if not next_refresh_token:
            raise RuntimeError("Token response missing refresh_token")
        expires_in = payload.get(
            "expiresIn",
            payload.get("expires_in", self._credentials.access_token_expires_in_seconds),
        )
        try:
            expires_in_seconds = int(expires_in)
            if expires_in_seconds <= 0:
                raise ValueError("Nonpositive expiry")
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Token response has invalid expires_in") from exc
        return RefreshResult(
            access_token=access_token,
            refresh_token=next_refresh_token,
            expires_in=expires_in_seconds,
            issued_at=int(time.time()),
        )

    def _refresh_request(self, refresh_token: str) -> dict[str, Any]:
        return self._token_request({"grant_type": "refresh_token", "refresh_token": refresh_token})

    def _token_request(self, parameters: dict[str, str]) -> dict[str, Any]:
        query = parse.urlencode(
            {
                **parameters,
                "client_id": self._credentials.client_id,
                "client_secret": self._credentials.secret,
            }
        )
        req = request.Request(
            f"{self._credentials.token_url}?{query}",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with request.urlopen(
                req, timeout=self._credentials.token_request_timeout_seconds
            ) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            # Error bodies and request URLs can echo credentials.
            exc.close()
            raise RuntimeError(f"Token request failed (HTTP {exc.code})") from None
        except URLError:
            raise RuntimeError("Token endpoint could not be reached") from None
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError("Token endpoint returned invalid JSON") from None
        if not isinstance(decoded, dict):
            raise RuntimeError("Token endpoint returned non-object payload")
        return decoded
