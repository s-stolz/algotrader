import unittest

import main
from fastapi.testclient import TestClient


class TestBacktesterServiceEntrypoint(unittest.TestCase):
    def test_fastapi_app_exposes_submission_and_status_routes(self) -> None:
        route_methods = set()
        for route in main.app.routes:
            path = getattr(route, "path", None)
            for method in getattr(route, "methods", set()):
                route_methods.add((path, method))

        self.assertIn(("/backtests", "POST"), route_methods)
        self.assertIn(("/backtests", "GET"), route_methods)
        self.assertIn(("/backtests/{run_id}", "GET"), route_methods)

    def test_health_endpoint_reports_ready(self) -> None:
        with TestClient(main.app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})


if __name__ == "__main__":
    unittest.main()
