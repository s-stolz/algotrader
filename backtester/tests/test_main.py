import unittest

import main
from fastapi.testclient import TestClient


class TestBacktesterServiceEntrypoint(unittest.TestCase):
    def test_fastapi_app_exposes_submission_and_status_routes(self) -> None:
        with TestClient(main.app) as client:
            response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        self.assertIn("post", paths["/backtests"])
        self.assertIn("get", paths["/backtests"])
        self.assertIn("get", paths["/backtests/{run_id}"])

    def test_health_endpoint_reports_ready(self) -> None:
        with TestClient(main.app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})


if __name__ == "__main__":
    unittest.main()
