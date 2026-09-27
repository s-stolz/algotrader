import type {
  BacktestBatch, BacktestRequestPayload, BacktestRun, StrategyCatalogEntry,
  SweepDraftState, SweepParameterDraft,
} from '@/types/backtesterContracts';

export type ReuseSource = {
  kind: 'run' | 'batch';
  id: string;
  strategyId: string;
  strategyVersion: number | null;
  historicalMetadata: StrategyCatalogEntry | null;
  defaultedParameters: string[];
};

export type ReuseDraft = {
  request: BacktestRequestPayload;
  sweep: SweepDraftState;
  source: ReuseSource;
};

const EMPTY_SWEEP: SweepDraftState = {
  isSweep: false, marketIds: [], timeframes: [], allowedDirections: [], parameters: {},
};

function copyJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function reuseStandalone(run: BacktestRun): ReuseDraft {
  const request = copyJson(run.request);
  request.run_metadata = null;
  return {
    request,
    sweep: copyJson(EMPTY_SWEEP),
    source: { kind: 'run', id: run.run_id, strategyId: request.strategy.strategy_id,
      strategyVersion: run.request_schema_version === 3 ? request.strategy.strategy_version ?? null : null,
      historicalMetadata: null, defaultedParameters: [] },
  };
}

export function reuseBatch(batch: BacktestBatch): ReuseDraft {
  const { shared_request: shared, normalized_selections: selections } = batch.accepted_definition;
  const firstMarket = selections.markets[0];
  const request = copyJson({
    ...shared,
    symbols: firstMarket ? [firstMarket.symbol] : [],
    exchange: firstMarket?.exchange ?? null,
    timeframe: selections.timeframes[0] ?? 'M1',
    run_metadata: null,
  }) as BacktestRequestPayload;
  const parameters: Record<string, SweepParameterDraft> = {};
  for (const [name, axis] of Object.entries(selections.parameters)) {
    const values = copyJson(axis.values);
    const schema = batch.strategy_metadata.parameters.find((parameter) => parameter.name === name);
    const choiceInput = schema?.type === 'bool' || Boolean(schema?.choices);
    const mode = axis.mode === 'range' ? 'range' : axis.mode === 'values' ? 'values' : 'constant';
    parameters[name] = {
      mode,
      valuesText: values.filter((value) => value !== null)
        .map((value) => JSON.stringify(value)).join('\n'),
      stringValues: values.filter((value): value is string => typeof value === 'string'),
      choiceIndexes: [], selectedChoiceValues: choiceInput ? values :
        values.filter((value) => value !== null),
      includeNull: !choiceInput && values.includes(null),
      rangeStart: axis.range?.start ?? null,
      rangeStop: axis.range?.stop ?? null,
      rangeStep: axis.range?.step ?? null,
    };
    if (mode === 'constant' && values.length) request.strategy.parameters[name] = values[0];
    if (axis.mode === 'default') delete request.strategy.parameters[name];
  }
  return {
    request,
    sweep: {
      isSweep: true,
      marketIds: selections.markets.map((market) => market.symbol_id),
      timeframes: [...selections.timeframes],
      allowedDirections: [...selections.allowed_directions],
      parameters,
    },
    source: { kind: 'batch', id: batch.batch_id, strategyId: batch.strategy_id,
      strategyVersion: batch.strategy_version,
      historicalMetadata: copyJson(batch.strategy_metadata),
      defaultedParameters: Object.entries(selections.parameters)
        .filter(([, axis]) => axis.mode === 'default').map(([name]) => name) },
  };
}
