import type {
  Backtest,
  BacktestCreationRequest,
  BacktestRun,
  StrategyCatalogEntry,
  BacktestSelectionsDraft,
  ParameterDraft,
} from '@/types/backtesterContracts';
import { normalizeExperimentName } from '@/types/backtesterContracts';

export type ReuseSource = {
  kind: 'run' | 'backtest';
  id: string;
  strategyId: string;
  strategyVersion: number | null;
  historicalMetadata: StrategyCatalogEntry | null;
};

export type ReuseDraft = {
  request: BacktestCreationRequest;
  selections: BacktestSelectionsDraft;
  source: ReuseSource;
};

const EMPTY_SELECTIONS: BacktestSelectionsDraft = {
  marketIds: [],
  timeframes: [],
  allowedDirections: [],
  parameters: {},
};

function copyJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function copyName(value: string | null | undefined): string {
  const name = normalizeExperimentName(value);
  const suffix = ' (copy)';
  return name ? [...name].slice(0, 120 - suffix.length).join('') + suffix : '';
}

export function reuseRun(
  run: BacktestRun,
  markets: { symbol_id: number; symbol: string; exchange: string }[],
): ReuseDraft {
  const request: BacktestCreationRequest = copyJson(run.request);
  request.name = '';
  request.run_metadata = null;
  return {
    request,
    selections: {
      ...copyJson(EMPTY_SELECTIONS),
      marketIds: markets
        .filter(
          (market) =>
            market.symbol === request.symbols[0] &&
            market.exchange === request.exchange,
        )
        .map((market) => market.symbol_id),
      timeframes: [request.timeframe],
      allowedDirections: [request.execution.allowed_directions],
    },
    source: {
      kind: 'run',
      id: run.run_id,
      strategyId: request.strategy.strategy_id,
      strategyVersion:
        run.request_schema_version === 3
          ? (request.strategy.strategy_version ?? null)
          : null,
      historicalMetadata: null,
    },
  };
}

export function reuseBacktest(backtest: Backtest): ReuseDraft {
  const { shared_request: shared, normalized_selections: selections } =
    backtest.accepted_definition;
  const firstMarket = selections.markets[0];
  const request = copyJson({
    ...shared,
    name: copyName(backtest.name),
    symbols: firstMarket ? [firstMarket.symbol] : [],
    exchange: firstMarket?.exchange ?? null,
    timeframe: selections.timeframes[0] ?? 'M1',
    run_metadata: null,
  }) as BacktestCreationRequest;
  const parameters: Record<string, ParameterDraft> = {};
  for (const [name, axis] of Object.entries(selections.parameters)) {
    const values = copyJson(axis.values);
    const schema = backtest.strategy_metadata.parameters.find(
      (parameter) => parameter.name === name,
    );
    const choiceInput = schema?.type === 'bool' || Boolean(schema?.choices);
    const mode =
      axis.mode === 'range'
        ? 'range'
        : axis.mode === 'values'
          ? 'values'
          : 'constant';
    parameters[name] = {
      mode,
      valuesText: values
        .filter((value) => value !== null)
        .map((value) => JSON.stringify(value))
        .join('\n'),
      stringValues: values.filter(
        (value): value is string => typeof value === 'string',
      ),
      choiceIndexes: [],
      selectedChoiceValues: choiceInput
        ? values
        : values.filter((value) => value !== null),
      includeNull: !choiceInput && values.includes(null),
      rangeStart: axis.range?.start ?? null,
      rangeStop: axis.range?.stop ?? null,
      rangeStep: axis.range?.step ?? null,
    };
    if (mode === 'constant' && values.length)
      request.strategy.parameters[name] = values[0];
  }
  return {
    request,
    selections: {
      marketIds: selections.markets.map((market) => market.symbol_id),
      timeframes: [...selections.timeframes],
      allowedDirections: [...selections.allowed_directions],
      parameters,
    },
    source: {
      kind: 'backtest',
      id: backtest.backtest_id,
      strategyId: backtest.strategy_id,
      strategyVersion: backtest.strategy_version,
      historicalMetadata: copyJson(backtest.strategy_metadata),
    },
  };
}
