import unittest

import main


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


if __name__ == "__main__":
    unittest.main()
