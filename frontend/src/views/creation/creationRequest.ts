import type {
  BacktestRequestPayload,
  StrategyCatalogEntry,
  StrategyParameterSchema,
  SweepDraftState,
  SweepParameterDraft,
  SweepPreviewRequest,
  SweepParameterAxis,
} from '@/types/backtesterContracts';
import { choiceValues } from './creationParameters';

export type DraftRequest = Omit<
  BacktestRequestPayload,
  'strategy' | 'run_metadata'
> & {
  strategy: {
    strategy_id: string;
    strategy_version?: number;
    parameters: Record<string, null | boolean | number | string>;
  };
  run_metadata: null;
  name?: string;
};

export function buildSweepRequest(
  draft: DraftRequest,
  sweep: SweepDraftState,
  selected: StrategyCatalogEntry | undefined,
  missingMarkets: string[],
  sweepParameter: (parameter: StrategyParameterSchema) => SweepParameterDraft,
  stringValues: (parameter: StrategyParameterSchema) => string[],
): SweepPreviewRequest {
  if (
    !selected ||
    selected.strategy_version !== draft.strategy.strategy_version
  ) {
    throw new Error('Review the current Strategy Version.');
  }
  if (
    !sweep.marketIds.length ||
    !sweep.timeframes.length ||
    !sweep.allowedDirections.length
  ) {
    throw new Error(
      'Select at least one Market, Timeframe, and Allowed Directions value.',
    );
  }
  if (missingMarkets.length)
    throw new Error('Replace unavailable saved Markets.');
  if (
    draft.start_ms <= 0 ||
    draft.end_ms <= draft.start_ms ||
    !Number.isFinite(draft.initial_capital) ||
    draft.initial_capital <= 0
  ) {
    throw new Error('Enter valid dates and initial capital.');
  }
  const parameter_axes: Record<string, SweepParameterAxis> = {};
  for (const parameter of selected.parameters) {
    const input = sweepParameter(parameter);
    if (input.mode === 'constant') {
      const value = draft.strategy.parameters[parameter.name];
      if (value === undefined) {
        if (parameter.required)
          throw new Error(`${parameter.name} is required.`);
        continue;
      }
      parameter_axes[parameter.name] = { mode: 'constant', value };
    } else if (input.mode === 'range') {
      if (
        input.rangeStart === null ||
        input.rangeStop === null ||
        input.rangeStep === null
      ) {
        throw new Error(`Enter Start, Stop, and Step for ${parameter.name}.`);
      }
      parameter_axes[parameter.name] = {
        mode: 'range',
        start: input.rangeStart,
        stop: input.rangeStop,
        step: input.rangeStep,
      };
    } else {
      let values: Array<null | boolean | number | string>;
      if (parameter.choices || parameter.type === 'bool') {
        values = (input.selectedChoiceValues ??
          input.choiceIndexes.map(
            (index) => choiceValues(parameter)[index],
          )) as Array<null | boolean | number | string>;
      } else if (parameter.type === 'str') {
        values = [...stringValues(parameter)];
      } else {
        values =
          input.valuesText === ''
            ? []
            : input.valuesText.split('\n').map((line) => {
                if (!line.trim())
                  throw new Error(
                    `Enter numeric values for ${parameter.name}.`,
                  );
                const value: unknown = JSON.parse(line);
                if (typeof value !== 'number' || !Number.isFinite(value)) {
                  throw new Error(
                    `Enter numeric values for ${parameter.name}.`,
                  );
                }
                return value;
              });
      }
      if (input.includeNull) values.push(null);
      if (!values.length || values.some((value) => value === undefined)) {
        throw new Error(`Select at least one value for ${parameter.name}.`);
      }
      parameter_axes[parameter.name] = { mode: 'values', values };
    }
  }
  const {
    symbols: _symbols,
    timeframe: _timeframe,
    exchange: _exchange,
    name: _name,
    ...shared
  } = draft;
  return {
    ...shared,
    strategy: {
      strategy_id: selected.strategy_id,
      strategy_version: selected.strategy_version,
    },
    markets: sweep.marketIds,
    timeframes: sweep.timeframes,
    parameter_axes,
    allowed_directions: sweep.allowedDirections,
  };
}

export function initialDraft(): DraftRequest {
  const end = new Date();
  const start = new Date(end.getTime() - 30 * 86_400_000);
  return {
    symbols: [],
    exchange: null,
    timeframe: 'M1',
    start_ms: Date.UTC(
      start.getUTCFullYear(),
      start.getUTCMonth(),
      start.getUTCDate(),
    ),
    end_ms: Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), end.getUTCDate()),
    strategy: { strategy_id: '', parameters: {} },
    initial_capital: 10_000,
    engine: 'vectorized',
    data_granularity: 'bar',
    persist_result: false,
    run_metadata: null,
    name: '',
    execution: {
      signal_timing: 'close',
      fill_timing: 'next_open',
      price_source: 'open',
      allow_partial_fills: false,
      allowed_directions: 'long_and_short',
      trade_accounting_policy: 'average_cost',
      gap_policy: 'skip',
      intrabar_exit_policy: 'conservative',
      commission_bps: 0,
      slippage_bps: 0,
    },
  };
}
