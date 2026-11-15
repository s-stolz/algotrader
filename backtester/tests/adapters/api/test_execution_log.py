import unittest

from adapters.api.app import create_app
from adapters.api.execution_log import get_execution_log_service
from app.execution_log import ExecutionLogService
from db_accessor_client import DatabaseAccessorClientError
from fastapi.testclient import TestClient


class ExecutionLogApiTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.saved = dict(
            run_id="run", status="succeeded", result_schema_version=3, total=21, items=[]
        )

        def read(run_id, page, page_size, include):
            self.calls.append((run_id, page, page_size, include))
            if run_id == "missing":
                raise DatabaseAccessorClientError("missing", status_code=404)
            return dict(self.saved, page=page, page_size=page_size)

        app = create_app()
        app.dependency_overrides[get_execution_log_service] = lambda: ExecutionLogService(read)
        self.client = TestClient(app)

    def test_bounded_page_and_empty_page_preserve_total(self):
        response = self.client.get(
            "/backtests/runs/run/execution-log?page=4&include_unexecuted=true"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(), dict(run_id="run", page=4, page_size=10, total=21, items=[])
        )
        self.assertEqual(self.calls, [("run", 4, 10, True)])

    def test_invalid_pagination_never_reads_storage(self):
        for query in ["page=0", "page_size=0", "page_size=101"]:
            self.assertEqual(
                self.client.get("/backtests/runs/run/execution-log?" + query).status_code, 422
            )
        self.assertEqual(self.calls, [])

    def test_ineligible_runs_conflict(self):
        for changes in [dict(status="running"), dict(result_schema_version=2)]:
            self.saved.update(status="succeeded", result_schema_version=3)
            self.saved.update(changes)
            self.assertEqual(self.client.get("/backtests/runs/run/execution-log").status_code, 409)

    def test_missing_is_distinct_from_successful_empty_run(self):
        self.saved.update(total=0)
        empty = self.client.get("/backtests/runs/run/execution-log")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json()["items"], [])
        self.assertEqual(self.client.get("/backtests/runs/missing/execution-log").status_code, 404)
