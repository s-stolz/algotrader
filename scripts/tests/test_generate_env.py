"""Runtime configuration contract tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

from scripts import generate_env

COMPOSE_PATH = generate_env.ROOT_DIR / "docker-compose.yml"


class GeneratedEnvironmentPreservationTests(unittest.TestCase):
    def test_tracked_topology_preserves_all_runtime_variables(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "topology_environment.json"
        expected = json.loads(fixture.read_text(encoding="utf-8"))
        topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)

        actual = generate_env.build_env(topology, {})

        self.assertEqual(list(actual), expected)

    def test_component_tuning_changes_only_its_runtime_variables(self) -> None:
        cases = (
            (
                "services.backtester.worker.poll_interval_seconds",
                2.5,
                "BACKTESTER_WORKER_POLL_INTERVAL_SECONDS",
            ),
            (
                "services.backtester.worker.heartbeat.interval_seconds",
                7.0,
                "BACKTESTER_WORKER_HEARTBEAT_INTERVAL_SECONDS",
            ),
            (
                "services.backtester.worker.heartbeat.stale_after_seconds",
                45.0,
                "BACKTESTER_WORKER_STALE_AFTER_SECONDS",
            ),
            (
                "services.backtester.sweeps.max_candidate_count",
                250,
                "BACKTESTER_MAX_SWEEP_CANDIDATE_COUNT",
            ),
            ("services.webserver.consumer.block_ms", 1234, "WEBSERVER_REDIS_BLOCK_MS"),
            ("services.webserver.consumer.batch_size", 17, "WEBSERVER_REDIS_BATCH_SIZE"),
            ("services.webserver.streams.queue_size", 31, "WEBSERVER_STREAM_QUEUE_SIZE"),
            ("services.webserver.streams.max_length", 500, "WEBSERVER_MAX_STREAM_LENGTH"),
            ("services.ingestion_service.consumer.block_ms", 2345, "CONSUMER_BLOCK_MS"),
            ("services.ingestion_service.consumer.batch_size", 19, "CONSUMER_BATCH_SIZE"),
            ("services.broker_service.streams.ticks.queue_size", 37, "BROKER_TICK_QUEUE_SIZE"),
            ("services.broker_service.streams.ticks.max_length", 321, "BROKER_TICK_STREAM_MAXLEN"),
            (
                "services.broker_service.streams.candles.max_length",
                654,
                "BROKER_CANDLE_STREAM_MAXLEN",
            ),
            (
                "services.broker_service.streams.limits.max_symbol_streams",
                3,
                "BROKER_MAX_SYMBOL_STREAMS",
            ),
            (
                "services.broker_service.streams.limits.max_trendbar_streams",
                4,
                "BROKER_MAX_TRENDBAR_STREAMS",
            ),
            (
                "services.broker_service.ctrader.request_timeout_seconds",
                12.5,
                "BROKER_CTRADER_REQUEST_TIMEOUT_SECONDS",
            ),
        )
        for path, value, env_key in cases:
            with self.subTest(path=path):
                topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
                expected = generate_env.build_env(topology, {})
                parent, field = path.rsplit(".", 1)
                generate_env.required(topology, parent)[field] = value
                expected[0][env_key] = str(value)

                self.assertEqual(generate_env.build_env(topology, {}), expected)

    def test_network_settings_keep_public_and_internal_addresses_distinct(self) -> None:
        topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
        topology["public"]["host"] = "workstation.local"
        topology["services"]["database_accessor_api"]["network"] = {
            "host": "market-db-api",
            "port": 8100,
            "published_port": 18100,
        }
        topology["services"]["webserver"]["network"]["websocket"] = {
            "port": 8766,
            "published_port": 18766,
        }
        topology["infrastructure"]["redis"]["network"] = {
            "host": "stream-store",
            "port": 6380,
            "published_port": 16380,
        }
        topology["infrastructure"]["redis"]["database"] = 2
        topology["services"]["broker_service"]["streams"]["redis_db"] = 3

        shared, _, _, _ = generate_env.build_env(topology, {})

        self.assertEqual(shared["DATABASE_ACCESSOR_BASE_URL"], "http://market-db-api:8100")
        self.assertEqual(shared["VITE_PROXY_DATA_ACCESSOR_TARGET"], "http://market-db-api:8100")
        self.assertEqual(shared["DATABASE_ACCESSOR_PUBLISHED_PORT"], "18100")
        self.assertEqual(shared["WEBSERVER_WS_PORT"], "8766")
        self.assertEqual(shared["VITE_WS_URL"], "ws://workstation.local:18766")
        self.assertEqual(shared["REDIS_URL"], "redis://stream-store:6380/2")
        self.assertEqual(shared["BROKER_REDIS_URL"], "redis://stream-store:6380/3")
        self.assertEqual(shared["REDIS_PUBLISHED_PORT"], "16380")


class DockerResourceConfigurationTests(unittest.TestCase):
    def test_every_compose_service_uses_generated_resources(self) -> None:
        topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
        compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
        configured_services = {
            name.replace("_", "-") for name in generate_env.DOCKER_RESOURCE_PATHS
        }
        self.assertEqual(configured_services, set(compose["services"]))
        topology["services"]["backtester"]["worker"]["resources"] = {
            "cpus": 0.75,
            "memory_reservation_mb": 768,
        }

        shared_env, _, _, _ = generate_env.build_env(topology, {})

        self.assertEqual(shared_env["COMPOSE_BACKTESTER_WORKER_CPUS"], "0.75")
        self.assertEqual(shared_env["COMPOSE_BACKTESTER_WORKER_MEMORY_RESERVATION"], "768m")
        for name, service in compose["services"].items():
            with self.subTest(service=name):
                prefix = f"COMPOSE_{name.upper().replace('-', '_')}"
                for field, suffix in (("cpus", "CPUS"), ("mem_reservation", "MEMORY_RESERVATION")):
                    key = f"{prefix}_{suffix}"
                    self.assertIn(key, shared_env)
                    self.assertEqual(service[field], f"${{{key}:?Run make config}}")
                self.assertNotIn("mem_limit", service)
                self.assertNotIn("oom_kill_disable", service)

    def test_invalid_resource_values_are_rejected(self) -> None:
        for field, values in (
            ("cpus", (0, -1, True, "1.0", float("inf"), float("nan"))),
            ("memory_reservation_mb", (0, -1, True, 128.5, "256m")),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
                    topology["infrastructure"]["redis"]["resources"][field] = value
                    with self.assertRaisesRegex(
                        ValueError, f"infrastructure.redis.resources.{field}"
                    ):
                        generate_env.build_env(topology, {})

    def test_missing_service_resources_are_rejected(self) -> None:
        for path in generate_env.DOCKER_RESOURCE_PATHS.values():
            for field in ("cpus", "memory_reservation_mb"):
                with self.subTest(path=path, field=field):
                    topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
                    del generate_env.required(topology, path)[field]
                    with self.assertRaisesRegex(ValueError, f"{path}.{field}"):
                        generate_env.build_env(topology, {})


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
        self.assertEqual(shared_env["BACKTESTER_WORKER_HEARTBEAT_INTERVAL_SECONDS"], "5.0")
        self.assertEqual(shared_env["BACKTESTER_WORKER_STALE_AFTER_SECONDS"], "30.0")
        self.assertEqual(shared_env["BACKTESTER_MAX_SWEEP_CANDIDATE_COUNT"], "1000")
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
        topology["infrastructure"]["timescaledb"]["database"]["user"] = "market_writer"
        topology["infrastructure"]["timescaledb"]["database"]["name"] = "market_history"

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
