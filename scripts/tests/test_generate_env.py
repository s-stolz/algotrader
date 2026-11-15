"""Runtime configuration contract tests."""

from __future__ import annotations

import json
import tempfile
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

    def test_broker_binding_and_actual_expiry_reach_only_their_consumers(self) -> None:
        topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
        shared, database, runtime, broker = generate_env.build_env(
            topology,
            {
                "ACCOUNT_ID": "123",
                "CTRADER_HOST_TYPE": "demo",
                "CTRADER_SECRET": "private",
                "CTRADER_ACCESS_TOKEN_ISSUED_AT": "1700000000",
                "CTRADER_ACCESS_TOKEN_EXPIRES_AT": "1700003600",
            },
        )
        self.assertEqual(runtime, {"ACCOUNT_ID": "123", "CTRADER_HOST_TYPE": "demo"})
        self.assertEqual(broker["CTRADER_ACCESS_TOKEN_EXPIRES_AT"], "1700003600")
        self.assertNotIn("CTRADER_SECRET", shared | database | runtime)
        self.assertEqual(shared["VITE_PROXY_INGESTION_TARGET"], "http://ingestion-service:8080")

    def test_component_tuning_changes_only_its_runtime_variables(self) -> None:
        cases = (
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
                "services.backtester.backtests.max_candidate_count",
                250,
                "BACKTESTER_MAX_BACKTEST_CANDIDATE_COUNT",
            ),
            (
                "services.realtime_service.consumer.block_ms",
                1234,
                "REALTIME_SERVICE_REDIS_BLOCK_MS",
            ),
            (
                "services.realtime_service.consumer.batch_size",
                17,
                "REALTIME_SERVICE_REDIS_BATCH_SIZE",
            ),
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
        topology["services"]["realtime_service"]["network"]["websocket"] = {
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

        self.assertEqual(shared["VITE_PROXY_DATA_ACCESSOR_TARGET"], "http://market-db-api:8100")
        self.assertEqual(shared["DATABASE_ACCESSOR_PUBLISHED_PORT"], "18100")
        self.assertEqual(shared["REALTIME_SERVICE_WS_PORT"], "8766")
        self.assertEqual(shared["VITE_WS_URL"], "ws://workstation.local:18766")
        self.assertEqual(shared["REDIS_URL"], "redis://stream-store:6380/2")
        self.assertEqual(shared["BROKER_REDIS_URL"], "redis://stream-store:6380/3")
        self.assertEqual(shared["REDIS_PUBLISHED_PORT"], "16380")


class NetworkPortConfigurationTests(unittest.TestCase):
    def test_compose_publishes_only_loopback_development_endpoints(self) -> None:
        compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
        shared = generate_env.build_env(generate_env.read_yaml(generate_env.TOPOLOGY_PATH), {})[0]
        expected = {
            "database-accessor-api": ("DATABASE_ACCESSOR", 18000, 8080),
            "indicator-api": ("INDICATOR_API", 18001, 8080),
            "backtester-api": ("BACKTESTER_API", 18002, 8080),
            "broker-service": ("BROKER_SERVICE", 18003, 8080),
            "ingestion-service": ("INGESTION_API", 18004, 8080),
            "realtime-service": ("REALTIME_SERVICE_WS", 18005, 8080),
            "frontend": ("FRONTEND", 5173, 5173),
            "timescaledb": ("TIMESCALEDB", 5432, 5432),
            "redis": ("REDIS", 6379, 6379),
        }
        for name, (prefix, published, internal) in expected.items():
            with self.subTest(service=name):
                ports = compose["services"][name]["ports"]
                self.assertEqual(len(ports), 1)
                target = (
                    str(internal)
                    if name in ("redis", "timescaledb")
                    else f"${{{prefix}_PORT:-{internal}}}"
                )
                self.assertEqual(
                    ports[0], f"127.0.0.1:${{{prefix}_PUBLISHED_PORT:-{published}}}:{target}"
                )
                self.assertEqual(shared[f"{prefix}_PUBLISHED_PORT"], str(published))
                self.assertEqual(shared[f"{prefix}_PORT"], str(internal))
        self.assertEqual(shared["REALTIME_SERVICE_HEALTH_PORT"], "8081")
        self.assertNotIn("REALTIME_SERVICE_HEALTH_PUBLISHED_PORT", shared)

    def test_only_actual_host_publications_must_be_unique(self) -> None:
        topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
        # A host endpoint can use a number shared by isolated container listeners.
        topology["services"]["frontend"]["network"]["published_port"] = 8080
        generate_env.build_env(topology, {})
        for path in (
            "services.broker_service.network",
            "services.realtime_service.network.websocket",
            "infrastructure.redis.network",
            "infrastructure.timescaledb.network",
        ):
            with self.subTest(path=path):
                topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
                generate_env.required(topology, path)["published_port"] = 18000
                with self.assertRaisesRegex(ValueError, "Duplicate published port 18000"):
                    generate_env.build_env(topology, {})

    def test_release_ignores_unused_development_publication_collisions(self) -> None:
        topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
        topology["mode"] = "production"
        topology["services"]["broker_service"]["network"]["published_port"] = 18000
        generate_env.build_env(topology, {})

    def test_invalid_ports_and_same_container_listener_conflicts_are_rejected(self) -> None:
        for field in ("port", "published_port"):
            for invalid in (0, 65536, -1, True, "8080", 8080.5, None):
                with self.subTest(field=field, invalid=invalid):
                    topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
                    topology["services"]["broker_service"]["network"][field] = invalid
                    with self.assertRaisesRegex(ValueError, "integer from 1 to 65535"):
                        generate_env.build_env(topology, {})
        topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
        topology["services"]["realtime_service"]["network"]["health"]["port"] = 8080
        with self.assertRaisesRegex(ValueError, "within their container"):
            generate_env.build_env(topology, {})

    def test_legacy_health_publication_override_is_ignored(self) -> None:
        topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
        expected = generate_env.build_env(topology, {})
        generate_env.merge_topology(
            topology,
            {"services": {"realtime_service": {"network": {"health": {"published_port": 8080}}}}},
        )
        self.assertEqual(generate_env.build_env(topology, {}), expected)
        self.assertNotIn(
            "published_port", topology["services"]["realtime_service"]["network"]["health"]
        )


class LocalTopologyTests(unittest.TestCase):
    def test_optional_override_preserves_defaults_and_replaces_explicit_null(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            shared = Path(directory) / "topology.yaml"
            local = Path(directory) / "topology.local.yaml"
            baseline = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
            baseline["services"]["broker_service"]["streams"]["ticks"]["max_length"] = 321
            shared.write_text(yaml.safe_dump(baseline), encoding="utf-8")
            self.assertEqual(generate_env.load_topology(shared, local), baseline)
            local.write_text(
                "services:\n  broker_service:\n    streams:\n"
                "      ticks:\n        max_length: null\n        queue_size: 42\n",
                encoding="utf-8",
            )
            merged = generate_env.load_topology(shared, local)
            baseline["services"]["broker_service"]["streams"]["ticks"].update(
                max_length=None, queue_size=42
            )
            self.assertEqual(merged, baseline)
            env = generate_env.build_env(merged, {})[0]
            self.assertEqual(env["BROKER_TICK_STREAM_MAXLEN"], "")
            self.assertEqual(env["BROKER_TICK_QUEUE_SIZE"], "42")
            self.assertEqual(
                generate_env.read_yaml(shared)["services"]["broker_service"]["streams"]["ticks"][
                    "max_length"
                ],
                321,
            )

    def test_invalid_override_structure_is_rejected(self) -> None:
        for overrides in ({"typo": 1}, {"services": None}, {"mode": []}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                generate_env.merge_topology(
                    generate_env.read_yaml(generate_env.TOPOLOGY_PATH), overrides
                )

    def test_invalid_history_is_rejected(self) -> None:
        cases = [
            (None, None),
            (90, "2020-01-01"),
            (0, None),
            (-1, None),
            (10**12, None),
            (True, None),
            (1.5, None),
            (None, "2020-02-30"),
            (None, "2999-01-01"),
            (None, "20200101"),
            (None, 2020),
        ]
        for days, start in cases:
            with self.subTest(days=days, start=start), self.assertRaises(ValueError):
                topology = generate_env.read_yaml(generate_env.TOPOLOGY_PATH)
                topology["services"]["ingestion_service"]["history"] = {
                    "lookback_days": days,
                    "start_date": start,
                }
                generate_env.build_env(topology, {})


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
        self.assertEqual(shared_env["BACKTESTER_API_PORT"], "8080")
        self.assertEqual(shared_env["BACKTESTER_API_PUBLISHED_PORT"], "18002")
        self.assertEqual(shared_env["BACKTESTER_LOG_LEVEL"], "INFO")
        self.assertEqual(shared_env["BACKTESTER_LOG_FORMAT"], "pretty")
        self.assertEqual(shared_env["BACKTESTER_WORKER_HEARTBEAT_INTERVAL_SECONDS"], "5.0")
        self.assertEqual(shared_env["BACKTESTER_WORKER_STALE_AFTER_SECONDS"], "30.0")
        self.assertEqual(shared_env["BACKTESTER_MAX_BACKTEST_CANDIDATE_COUNT"], "1000")
        self.assertEqual(
            shared_env["VITE_PROXY_BACKTESTER_TARGET"],
            "http://backtester-api:8080",
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
            ["127.0.0.1:${BACKTESTER_API_PUBLISHED_PORT:-18002}:${BACKTESTER_API_PORT:-8080}"],
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
