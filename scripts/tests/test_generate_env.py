"""Runtime configuration contract tests."""

from __future__ import annotations

import unittest

import yaml

from scripts import generate_env

COMPOSE_PATH = generate_env.ROOT_DIR / "docker-compose.yml"


class BacktesterRuntimeConfigurationTests(unittest.TestCase):
    def test_tracked_topology_generates_backtester_runtime_environment(self) -> None:
        topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)

        shared_env, _, _, _ = generate_env.build_env(topology, {})

        self.assertEqual(shared_env["BACKTESTER_API_HOST"], "backtester-api")
        self.assertEqual(shared_env["BACKTESTER_API_PORT"], "8020")
        self.assertEqual(shared_env["BACKTESTER_API_PUBLISHED_PORT"], "8020")
        self.assertEqual(shared_env["BACKTESTER_LOG_LEVEL"], "INFO")
        self.assertEqual(shared_env["BACKTESTER_LOG_FORMAT"], "pretty")
        self.assertEqual(shared_env["BACKTESTER_WORKER_POLL_INTERVAL_SECONDS"], "1.0")
        self.assertEqual(
            shared_env["VITE_PROXY_BACKTESTER_TARGET"],
            "http://backtester-api:8020",
        )

    def test_compose_runs_api_and_singleton_worker_from_same_image(self) -> None:
        compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
        services = compose["services"]

        api = services["backtester-api"]
        worker = services["backtester-worker"]

        self.assertEqual(api["image"], worker["image"])
        self.assertEqual(api["build"], worker["build"])
        self.assertEqual(api["command"], ["python", "main.py"])
        self.assertEqual(worker["command"], ["python", "worker.py"])
        self.assertEqual(
            api["depends_on"]["database-accessor-api"]["condition"],
            "service_healthy",
        )
        self.assertEqual(
            worker["depends_on"]["database-accessor-api"]["condition"],
            "service_healthy",
        )
        self.assertEqual(
            api["ports"],
            ["${BACKTESTER_API_PUBLISHED_PORT:-8020}:${BACKTESTER_API_PORT:-8020}"],
        )
        self.assertIn("healthcheck", api)
        self.assertNotIn("ports", worker)
        self.assertEqual(
            [name for name in services if name.startswith("backtester-worker")],
            ["backtester-worker"],
        )


class TimescaleRuntimeConfigurationTests(unittest.TestCase):
    def test_tracked_database_topology_generates_postgres_image_environment(self) -> None:
        topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
        topology["infrastructure"]["timescaledb"]["user"] = "market_writer"
        topology["infrastructure"]["timescaledb"]["database"] = "market_history"

        shared_env, db_secrets_env, _, _ = generate_env.build_env(
            topology,
            {"TIMESCALEDB_PASSWORD": "local-password"},
        )

        self.assertEqual(shared_env["TIMESCALEDB_USER"], "market_writer")
        self.assertEqual(shared_env["TIMESCALEDB_DB"], "market_history")
        self.assertEqual(shared_env["POSTGRES_USER"], "market_writer")
        self.assertEqual(shared_env["POSTGRES_DB"], "market_history")
        self.assertNotIn("POSTGRES_PASSWORD", shared_env)
        self.assertEqual(db_secrets_env["POSTGRES_PASSWORD"], "local-password")

    def test_compose_uses_generated_environment_with_self_contained_database_image(
        self,
    ) -> None:
        compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))

        timescaledb = compose["services"]["timescaledb"]

        self.assertEqual(
            timescaledb["build"],
            {
                "context": ".",
                "dockerfile": "timescaledb-init/Dockerfile",
            },
        )
        self.assertEqual(timescaledb["image"], "algotrader-timescaledb")
        self.assertEqual(
            timescaledb["env_file"],
            ["./config/.env.shared", "./config/.env.secrets.db"],
        )
        self.assertNotIn("environment", timescaledb)
        self.assertNotIn(
            "./timescaledb-init:/docker-entrypoint-initdb.d",
            timescaledb["volumes"],
        )


if __name__ == "__main__":
    unittest.main()
