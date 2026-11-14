import type { Backtest } from './backtests';
import type { BacktestRun } from './history';
import type { StrategyParameterSchema } from './requests';
import { scheduleLabel } from './schedule';

export type DimensionValue = string | number | boolean | null;
export type HeatmapDimension = {
  key: string;
  label: string;
  numeric: boolean;
  options: { value: string; label: string }[];
};
export type HeatmapMember = {
  run: BacktestRun;
  inputs: Record<string, string>;
};
export type HeatmapSnapshot = {
  backtestId: string;
  dimensions: HeatmapDimension[];
  members: HeatmapMember[];
  byTuple: Map<string, HeatmapMember>;
};
export const valueKey = (value: DimensionValue) => JSON.stringify(value);
export const tupleKey = (
  dimensions: HeatmapDimension[],
  inputs: Record<string, string>,
) => JSON.stringify(dimensions.map((dimension) => inputs[dimension.key]));

export function terminalMembersIssue(
  backtest: Backtest,
  runs: BacktestRun[],
): string | null {
  if (!['completed', 'cancelled'].includes(backtest.status))
    return 'Backtest is still active.';
  if (
    runs.length !== backtest.member_count ||
    runs.length !== backtest.total_count
  )
    return 'The saved member list is incomplete.';
  const ids = new Set<string>();
  const counts = { succeeded: 0, failed: 0, cancelled: 0 };
  for (const [index, run] of runs.entries()) {
    if (
      !run.run_id ||
      ids.has(run.run_id) ||
      run.backtest_id !== backtest.backtest_id ||
      run.run_ordinal !== index
    )
      return 'Saved Run identities or ordinals are invalid.';
    ids.add(run.run_id);
    if (
      run.status !== 'succeeded' &&
      run.status !== 'failed' &&
      run.status !== 'cancelled'
    )
      return 'The saved member list is not yet terminal.';
    counts[run.status]++;
  }
  if (
    Object.entries(counts).some(
      ([status, count]) =>
        count !== backtest.outcome_counts[status as keyof typeof counts],
    )
  )
    return 'Saved member outcomes do not match the Backtest.';
  return null;
}

function validParameter(
  value: unknown,
  schema: StrategyParameterSchema,
): value is DimensionValue {
  if (value === null) return schema.nullable;
  if (schema.type === 'bool') return typeof value === 'boolean';
  if (schema.type === 'str') return typeof value === 'string';
  return (
    typeof value === 'number' &&
    Number.isFinite(value) &&
    (schema.type !== 'int' || Number.isInteger(value))
  );
}

function dimension(
  key: string,
  label: string,
  values: DimensionValue[],
  numeric = false,
  labels?: string[],
): HeatmapDimension {
  if (!values.length || new Set(values.map(valueKey)).size !== values.length)
    throw new Error(`Invalid saved domain for ${label}.`);
  const options = values.map((value, index) => ({
    value: valueKey(value),
    label: labels?.[index] ?? (value === null ? '—' : String(value)),
  }));
  if (numeric)
    options.sort((a, b) => {
      const left = JSON.parse(a.value),
        right = JSON.parse(b.value);
      return left === null ? 1 : right === null ? -1 : left - right;
    });
  return { key, label, numeric, options };
}

// Historical meaning comes exclusively from the accepted schema/domains and requests.
export function adaptHeatmapSnapshot(
  backtest: Backtest,
  runs: BacktestRun[],
): HeatmapSnapshot {
  const issue = terminalMembersIssue(backtest, runs);
  if (issue) throw new Error(issue);
  const saved = backtest.accepted_definition.normalized_selections;
  const schemas = backtest.strategy_metadata.parameters;
  if (
    new Set(schemas.map((schema) => schema.name)).size !== schemas.length ||
    Object.keys(saved.parameters).length !== schemas.length
  )
    throw new Error('Saved parameter schema and domains disagree.');
  const dimensions = schemas.map((schema) => {
    const values = saved.parameters[schema.name]?.values;
    if (
      !Array.isArray(values) ||
      !values.every((value) => validParameter(value, schema))
    )
      throw new Error(`Invalid saved values for ${schema.name}.`);
    return dimension(
      `parameter:${schema.name}`,
      schema.display_name ?? schema.name,
      values as DimensionValue[],
      schema.type === 'int' || schema.type === 'float',
    );
  });
  const scheduleKey = (
    schedule: BacktestRun['request']['execution']['daily_schedule'],
  ) =>
    schedule == null
      ? null
      : JSON.stringify([
          schedule.entry_start_minute_utc,
          schedule.last_entry_minute_utc,
          schedule.exit_minute_utc,
        ]);
  const schedules = saved.daily_schedules ?? [null];
  dimensions.push(
    dimension(
      'market',
      'Market',
      saved.markets.map((market) => market.symbol_id),
      false,
      saved.markets.map(
        (market) =>
          `${market.symbol} · ${market.exchange} (#${market.symbol_id})`,
      ),
    ),
    dimension('timeframe', 'Timeframe', saved.timeframes),
    dimension(
      'direction',
      'Allowed Directions',
      saved.allowed_directions,
      false,
      saved.allowed_directions.map(
        (value) =>
          ({
            long_only: 'Long only',
            short_only: 'Short only',
            long_and_short: 'Long and short',
          })[value],
      ),
    ),
    dimension(
      'schedule',
      'Daily schedule (UTC)',
      schedules.map(scheduleKey),
      false,
      schedules.map(scheduleLabel),
    ),
  );
  if (
    dimensions.reduce((count, field) => count * field.options.length, 1) !==
    backtest.raw_count
  )
    throw new Error(
      'Saved dimension domains do not match the candidate count.',
    );
  const byTuple = new Map<string, HeatmapMember>();
  const members = runs.map((run) => {
    const request = run.request;
    if (
      request.strategy.strategy_id !== backtest.strategy_id ||
      request.strategy.strategy_version !== backtest.strategy_version ||
      Object.keys(request.strategy.parameters).length !== schemas.length
    )
      throw new Error(
        `Run #${run.run_ordinal + 1} disagrees with the saved strategy.`,
      );
    const markets = saved.markets.filter((market) =>
      request.instrument
        ? market.symbol_id === request.instrument.symbol_id
        : request.symbols.length === 1 &&
          market.symbol === request.symbols[0] &&
          market.exchange === request.exchange,
    );
    if (markets.length !== 1)
      throw new Error('A Run has an ambiguous or unknown saved Market.');
    const inputs: Record<string, string> = {
      market: valueKey(markets[0].symbol_id),
      timeframe: valueKey(request.timeframe),
      direction: valueKey(request.execution.allowed_directions),
      schedule: valueKey(scheduleKey(request.execution.daily_schedule)),
    };
    for (const schema of schemas) {
      const value = request.strategy.parameters[schema.name];
      if (
        !Object.hasOwn(request.strategy.parameters, schema.name) ||
        !validParameter(value, schema)
      )
        throw new Error(
          `Run #${run.run_ordinal + 1} has a missing or invalid ${schema.name}.`,
        );
      inputs[`parameter:${schema.name}`] = valueKey(value);
    }
    for (const field of dimensions) {
      if (!field.options.some((option) => option.value === inputs[field.key]))
        throw new Error(
          `Run #${run.run_ordinal + 1} is outside the saved ${field.label} domain.`,
        );
    }
    const key = tupleKey(dimensions, inputs);
    if (byTuple.has(key))
      throw new Error(
        'Multiple saved Runs have the same full input combination.',
      );
    const member = { run, inputs };
    byTuple.set(key, member);
    return member;
  });
  return { backtestId: backtest.backtest_id, dimensions, members, byTuple };
}
