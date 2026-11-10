import type { DailyTradingSchedule } from '@/types/backtest/schedule';
import { setupIssues } from './setup/setupValidation';
import type {
  BacktestRequestPayload,
  StrategyCatalogEntry,
  StrategyParameterSchema,
  BacktestSelectionsDraft,
  ParameterDraft,
  BacktestPreviewRequest,
  ParameterAxis,
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

export function buildBacktestRequest(
  draft: DraftRequest,
  selections: BacktestSelectionsDraft,
  selected: StrategyCatalogEntry | undefined,
  missingMarkets: string[],
  parameterInput: (parameter: StrategyParameterSchema) => ParameterDraft,
  stringValues: (parameter: StrategyParameterSchema) => string[],
): BacktestPreviewRequest {
  draft = {
    ...draft,
    execution: {
      ...draft.execution,
      execution_mode: selected?.execution_mode ?? 'targets',
    },
  };
  const issues = setupIssues(
    draft,
    selections,
    !selected || selected.strategy_version !== draft.strategy.strategy_version,
    missingMarkets,
    selected,
  );
  const firstIssue = Object.values(issues)[0];
  if (firstIssue) throw new Error(firstIssue);
  if (!selected) throw new Error('Select a strategy.');
  const parameter_axes: Record<string, ParameterAxis> = {};
  for (const parameter of selected.parameters) {
    const input = parameterInput(parameter);
    if (input.mode === 'constant' || parameter.purpose) {
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
    market_min_move: _marketMinMove,
    instrument: _instrument,
    name: _name,
    ...shared
  } = draft;
  const execution = { ...shared.execution };
  execution.sizing ??= { mode: 'strategy', value: null, leverage: 1 };
  delete execution.daily_schedule;
  if (execution.execution_mode === 'orders') {
    execution.candle_quote ??= 'mid';
    execution.intrabar_execution_policy ??=
      execution.intrabar_exit_policy === 'take_profit_first'
        ? 'optimistic'
        : execution.intrabar_exit_policy === 'error'
          ? 'error'
          : 'conservative';
    execution.intrabar_exit_policy = {
      conservative: 'conservative',
      optimistic: 'take_profit_first',
      error: 'error',
    }[
      execution.intrabar_execution_policy
    ] as typeof execution.intrabar_exit_policy;
  } else {
    delete execution.candle_quote;
    delete execution.spread;
    delete execution.max_position_quantity;
    delete execution.intrabar_execution_policy;
  }
  return {
    ...shared,
    execution,
    ...(selections.dailySchedule.enabled
      ? {
          daily_schedules: selections.dailySchedule.candidates.map(
            (candidate) => ({ ...candidate }) as DailyTradingSchedule,
          ),
        }
      : {}),
    strategy: {
      strategy_id: selected.strategy_id,
      strategy_version: selected.strategy_version,
    },
    markets: selections.marketIds,
    timeframes: selections.timeframes,
    parameter_axes,
    allowed_directions: selections.allowedDirections,
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
    run_metadata: null,
    name: '',
    execution: {
      candle_quote: 'mid',
      sizing: { mode: 'strategy', value: null, leverage: 1 },
      stop_loss: { mode: 'strategy', value: null },
      take_profit: { mode: 'strategy', value: null },
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
