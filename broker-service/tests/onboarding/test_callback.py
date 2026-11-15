from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlsplit

from app.onboarding.callback import CallbackSession


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
        self.assertIsNone(result.pairing_code)
        with self.assertRaises(ValueError):
            session.receive(path, "localhost:8080", cookie)

    def test_missing_provider_state_requires_explicit_terminal_pairing(self) -> None:
        session = self.session()
        result = session.receive(
            "/redirect?code=code", "localhost:8080", f"algotrader_oauth={session.browser_token}"
        )
        self.assertIsNotNone(result.pairing_code)
