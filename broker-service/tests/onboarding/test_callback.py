from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlsplit

from app.onboarding.callback import AuthorizationStateError, CallbackSession


class CallbackTests(unittest.TestCase):
    def session(self) -> CallbackSession:
        session = CallbackSession("public-client", "accounts")
        session.started = True
        return session

    def test_requested_permission_and_state_are_in_authorization_link(self) -> None:
        session = CallbackSession("public-client", "trading")
        query = parse_qs(urlsplit(session.authorization_url).query)
        self.assertEqual(query["scope"], ["trading"])
        self.assertEqual(query["state"], [session.state])
        self.assertEqual(query["redirect_uri"], ["http://localhost:8080/redirect"])

    def test_unsolicited_wrong_host_wrong_cookie_and_wrong_state_are_rejected(self) -> None:
        session = self.session()
        cookie = f"algotrader_oauth={session.browser_token}"
        for path, host, cookies in (
            ("/redirect?code=code", "evil.example:8080", cookie),
            ("/redirect?code=code", "localhost:8080", ""),
            ("/redirect?code=code&state=wrong", "localhost:8080", cookie),
        ):
            with self.subTest(path=path, host=host, cookies=cookies):
                with self.assertRaises(ValueError):
                    session.receive(path, host, cookies)
                self.assertIsNone(session.result)
        session.started = False
        with self.assertRaises(ValueError):
            session.receive("/redirect?code=code", "localhost:8080", cookie)

    def test_matching_state_accepts_only_once(self) -> None:
        session = self.session()
        path = f"/redirect?code=code&state={session.state}"
        cookie = f"algotrader_oauth={session.browser_token}"
        result = session.receive(path, "localhost:8080", cookie)
        self.assertEqual(result.code, "code")
        with self.assertRaises(ValueError):
            session.receive(path, "localhost:8080", cookie)

    def test_missing_empty_duplicate_or_wrong_state_rejects_even_with_browser_cookie(self) -> None:
        for query in ("", "&state=", "&state=attacker", "&state=one&state=two"):
            session = self.session()
            with self.subTest(query=query):
                with self.assertRaisesRegex(
                    AuthorizationStateError, "state is missing or does not match"
                ):
                    session.receive(
                        "/redirect?code=attacker-code" + query,
                        "localhost:8080",
                        f"algotrader_oauth={session.browser_token}",
                    )
                self.assertIsNone(session.result)


class CallbackHTTPTests(unittest.TestCase):
    def test_real_http_handshake_requires_the_original_authorization_state(self) -> None:
        import os
        import threading
        from http.client import HTTPConnection
        from http.server import HTTPServer
        from unittest.mock import patch

        from app.onboarding.callback import wait_for_callback

        if os.getenv("RUN_BROKER_CALLBACK_HTTP_TESTS") != "1":
            self.skipTest("Set RUN_BROKER_CALLBACK_HTTP_TESTS=1 for loopback HTTP integration")
        for valid_state in (True, False):
            with self.subTest(valid_state=valid_state):
                session = CallbackSession("public-client", "accounts")
                ready = threading.Event()
                servers: list[HTTPServer] = []
                failures: list[BaseException] = []
                results = []

                def make_server(address, handler):
                    server = HTTPServer((address[0], 0), handler)
                    servers.append(server)
                    return server

                def listen():
                    try:
                        results.append(
                            wait_for_callback(
                                session, timeout_seconds=5, announce=lambda _message: ready.set()
                            )
                        )
                    except BaseException as exc:
                        failures.append(exc)

                with patch("app.onboarding.callback.HTTPServer", side_effect=make_server):
                    worker = threading.Thread(target=listen, daemon=True)
                    worker.start()
                    self.assertTrue(ready.wait(5), "Callback server did not start")
                    connection = HTTPConnection("127.0.0.1", servers[0].server_port, timeout=5)
                    try:
                        connection.request(
                            "GET", session.start_path, headers={"Host": "localhost:8080"}
                        )
                        start = connection.getresponse()
                        self.assertEqual(start.status, 302)
                        self.assertEqual(
                            parse_qs(urlsplit(start.getheader("Location") or "").query)["state"],
                            [session.state],
                        )
                        cookie = (start.getheader("Set-Cookie") or "").split(";", 1)[0]
                        start.read()
                        query = f"&state={session.state}" if valid_state else ""
                        connection.request(
                            "GET",
                            "/redirect?code=provider-code" + query,
                            headers={"Host": "localhost:8080", "Cookie": cookie},
                        )
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200 if valid_state else 400)
                        response.read()
                    finally:
                        connection.close()
                        worker.join(timeout=6)
                self.assertFalse(worker.is_alive())
                if valid_state:
                    self.assertEqual(results[0].code, "provider-code")
                    self.assertFalse(failures)
                else:
                    self.assertFalse(results)
                    self.assertIsInstance(failures[0], AuthorizationStateError)
                    self.assertIsNone(session.result)
