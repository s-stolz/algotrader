import unittest
from typing import Annotated, Mapping, cast

from domain.types import StrategyConfig
from strategies import registry
from strategies.base import IndicatorFeatureRequirement, ProtectiveExitSpec, StrategyDefinition
from strategies.registry import (
    InvalidParameterCombinationError,
    ParameterInfo,
    StrategyVersionUnavailableError,
    register_strategy,
    reject_combination,
    resolve_strategy,
    strategy_catalog,
    validate_parameters,
)


class TestStrategyRegistry(unittest.TestCase):
    def test_catalog_derives_order_types_defaults_and_constraints_from_builder(self) -> None:
        def validate(parameters: Mapping[str, object]) -> None:
            if parameters["label"] == "reject":
                reject_combination("label", "count", message="Label and count are incompatible")

        @register_strategy("test_schema", 7, validator=validate)
        def builder(
            *,
            enabled: bool,
            count: Annotated[int, ParameterInfo(minimum=1, maximum=4)] = 2,
            ratio: Annotated[float, ParameterInfo(choices=(0.5, 1.0))] = 0.5,
            label: Annotated[str, ParameterInfo(choices=("a", "reject"))] = "a",
            note: str | None = None,
        ) -> StrategyDefinition:
            raise AssertionError("Validation must not execute the strategy")

        try:
            catalog = next(
                item for item in strategy_catalog() if item["strategy_id"] == "test_schema"
            )
            self.assertEqual(catalog["strategy_version"], 7)
            fields = cast(list[dict[str, object]], catalog["parameters"])
            self.assertEqual(
                [field["name"] for field in fields],
                [
                    "enabled",
                    "count",
                    "ratio",
                    "label",
                    "note",
                ],
            )
            self.assertTrue(fields[0]["required"])
            self.assertNotIn("default", fields[0])
            self.assertEqual(fields[1]["minimum"], 1)
            self.assertEqual(fields[1]["maximum"], 4)
            self.assertEqual(fields[2]["choices"], [0.5, 1.0])
            self.assertTrue(fields[4]["nullable"])

            config = StrategyConfig("test_schema", {"enabled": True, "ratio": 1}, 7)
            resolved = validate_parameters(config)
            self.assertEqual(
                resolved.parameters,
                {
                    "enabled": True,
                    "count": 2,
                    "ratio": 1.0,
                    "label": "a",
                    "note": None,
                },
            )
            self.assertEqual(
                validate_parameters(
                    StrategyConfig(
                        "test_schema",
                        {"enabled": False, "note": None},
                        7,
                    )
                ).parameters["note"],
                None,
            )
            invalid = (
                ({}, "Missing required"),
                ({"enabled": 1}, "enabled must be bool"),
                ({"enabled": True, "count": True}, "count must be int"),
                ({"enabled": True, "count": 5}, "count must be at most"),
                ({"enabled": True, "ratio": 0.75}, "ratio must be one of"),
                ({"enabled": True, "label": None}, "label cannot be null"),
            )
            for values, message in invalid:
                with self.subTest(values=values), self.assertRaisesRegex(ValueError, message):
                    validate_parameters(StrategyConfig("test_schema", values, 7))
            with self.assertRaises(InvalidParameterCombinationError) as context:
                validate_parameters(
                    StrategyConfig(
                        "test_schema",
                        {"enabled": True, "label": "reject"},
                        7,
                    )
                )
            self.assertEqual(context.exception.code, "invalid_parameter_combination")
            self.assertEqual(context.exception.fields, ("label", "count"))
            with self.assertRaises(StrategyVersionUnavailableError):
                validate_parameters(StrategyConfig("test_schema", {"enabled": True}, 6))
        finally:
            registry._REGISTRY.pop("test_schema", None)

    def test_unsupported_parameter_type_fails_registration(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported parameter type"):

            @register_strategy("unsupported", 1)
            def unsupported(*, values: list[int]) -> StrategyDefinition:
                raise AssertionError(values)

        self.assertNotIn("unsupported", registry._REGISTRY)

    def test_builtin_numeric_limits_match_execution_contract(self) -> None:
        catalog = next(
            item for item in strategy_catalog() if item["strategy_id"] == "sma_crossover"
        )
        fields = cast(list[dict[str, object]], catalog["parameters"])
        quantity = next(field for field in fields if field["name"] == "quantity")
        stop = next(field for field in fields if field["name"] == "stop_loss_pct")
        self.assertTrue(quantity["exclusive_minimum"])
        self.assertTrue(stop["exclusive_maximum"])
        for parameters in ({"quantity": 0}, {"stop_loss_pct": 0}, {"stop_loss_pct": 100}):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                validate_parameters(StrategyConfig("sma_crossover", parameters, 1))

    def test_resolves_sma_crossover_from_request_parameters(self) -> None:
        strategy = resolve_strategy(
            StrategyConfig(
                strategy_id="sma_crossover",
                parameters={"fast_window": 2, "slow_window": 3, "quantity": 2.5},
            )
        )

        self.assertEqual(strategy.strategy_id, "sma_crossover")
        self.assertEqual(strategy.feature_specs, ("sma_fast", "sma_slow"))
        self.assertEqual(strategy.metadata["warmup_bars"], 3)
        self.assertEqual(
            strategy.indicator_requirements,
            (
                IndicatorFeatureRequirement(
                    feature_name="sma_fast",
                    indicator_id="sma",
                    output_key="sma",
                    parameters={"window": 2, "source": "close"},
                ),
                IndicatorFeatureRequirement(
                    feature_name="sma_slow",
                    indicator_id="sma",
                    output_key="sma",
                    parameters={"window": 3, "source": "close"},
                ),
            ),
        )
        self.assertTrue(strategy.is_v1_parity_compatible)
        self.assertEqual(strategy.require_v1_parity_model().protective_exit, ProtectiveExitSpec())

    def test_resolves_sma_crossover_stop_loss_parameter(self) -> None:
        strategy = resolve_strategy(
            StrategyConfig(
                strategy_id="sma_crossover",
                parameters={
                    "fast_window": 2,
                    "slow_window": 3,
                    "quantity": 2.5,
                    "stop_loss_pct": 4.0,
                },
            )
        )

        self.assertEqual(
            strategy.require_v1_parity_model().protective_exit,
            ProtectiveExitSpec(stop_loss_pct=4.0),
        )

    def test_resolves_sma_crossover_take_profit_parameter(self) -> None:
        strategy = resolve_strategy(
            StrategyConfig(
                strategy_id="sma_crossover",
                parameters={
                    "fast_window": 2,
                    "slow_window": 3,
                    "quantity": 2.5,
                    "take_profit_pct": 8.0,
                },
            )
        )

        self.assertEqual(
            strategy.require_v1_parity_model().protective_exit,
            ProtectiveExitSpec(take_profit_pct=8.0),
        )

    def test_unknown_strategy_id_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown strategy_id 'not_registered'"):
            resolve_strategy(StrategyConfig(strategy_id="not_registered"))

    def test_invalid_strategy_parameters_fail_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid parameters for strategy 'sma_crossover'"):
            resolve_strategy(
                StrategyConfig(
                    strategy_id="sma_crossover",
                    parameters={"fast_window": 2, "slow_window": 3, "quantity": 1.0, "extra": 5},
                )
            )


if __name__ == "__main__":
    unittest.main()
