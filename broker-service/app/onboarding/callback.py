from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlsplit

REDIRECT_URI = "http://localhost:8080/redirect"
AUTHORIZATION_URI = "https://id.ctrader.com/my/settings/openapi/grantingaccess/"


@dataclass(frozen=True)
class AuthorizationCallback:
    code: str
    pairing_code: str | None = None


class CallbackSession:
    def __init__(self, client_id: str, scope: str) -> None:
        if scope not in {"accounts", "trading"}:
            raise ValueError("Choose accounts or trading authorization")
        self.state = secrets.token_urlsafe(32)
        self.browser_token = secrets.token_urlsafe(32)
        self.start_path = "/start/" + secrets.token_urlsafe(32)
        self.authorization_url = (
            AUTHORIZATION_URI
            + "?"
            + urlencode(
                {
                    "client_id": client_id,
                    "redirect_uri": REDIRECT_URI,
                    "scope": scope,
                    "state": self.state,
                }
            )
        )
        self.result: AuthorizationCallback | None = None
        self.error: str | None = None
        self.started = False

    def receive(self, path: str, host: str, cookie_header: str) -> AuthorizationCallback:
        if host != "localhost:8080" or not self.started or self.result is not None:
            raise ValueError("Unexpected authorization callback")
        cookies = SimpleCookie()
        try:
            cookies.load(cookie_header)
        except CookieError:
            raise ValueError("Invalid authorization cookie") from None
        cookie = cookies.get("algotrader_oauth")
        if cookie is None or not secrets.compare_digest(cookie.value, self.browser_token):
            raise ValueError("Authorization browser does not match setup")
        parsed = urlsplit(path)
        if parsed.path != "/redirect":
            raise ValueError("Unexpected callback path")
        query = parse_qs(parsed.query)
        if "state" in query and query["state"] != [self.state]:
            raise ValueError("Authorization state does not match setup")
        if "error" in query:
            raise ValueError("Broker authorization was declined")
        codes = query.get("code", [])
        if len(codes) != 1 or not codes[0] or len(codes[0]) > 4096:
            raise ValueError("Authorization code is missing or invalid")
        # The provider's documented flow does not promise to echo OAuth state.
        # Without it, require deliberate pairing in the terminal, never auto-accept.
        pairing_code = None if "state" in query else secrets.token_hex(4).upper()
        self.result = AuthorizationCallback(codes[0], pairing_code)
        return self.result


def wait_for_callback(
    session: CallbackSession,
    *,
    timeout_seconds: float = 300,
    announce: Callable[[str], None] = print,
    bind_address: str = "127.0.0.1",
) -> AuthorizationCallback:
    class Handler(BaseHTTPRequestHandler):
        timeout = 5.0

        def log_message(self, format: str, *args: object) -> None:
            pass

        def do_GET(self) -> None:  # noqa: N802
            if self.headers.get("Host") != "localhost:8080":
                self.send_error(400, "Unexpected callback host")
                return
            if self.path == session.start_path and not session.started:
                session.started = True
                self.send_response(302)
                self.send_header("Location", session.authorization_url)
                self.send_header(
                    "Set-Cookie",
                    f"algotrader_oauth={session.browser_token}; "
                    "HttpOnly; SameSite=Lax; Path=/; Max-Age=300",
                )
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            try:
                result = session.receive(
                    self.path, self.headers.get("Host", ""), self.headers.get("Cookie", "")
                )
            except ValueError:
                self.send_error(
                    400, "Authorization callback rejected. Return to the setup terminal."
                )
                return
            text = "Authorization received. Return to the setup terminal to select your account."
            if result.pairing_code:
                text = f"Enter this pairing code in your setup terminal: {result.pairing_code}"
            content = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

    with HTTPServer((bind_address, 8080), Handler) as server:
        server.timeout = 1
        announce("Open this link in your browser: http://localhost:8080" + session.start_path)
        deadline = time.monotonic() + timeout_seconds
        while session.result is None and time.monotonic() < deadline:
            server.handle_request()
        if session.result is None:
            raise TimeoutError("Authorization timed out; run setup again")
    return session.result
