import {
  type JsonValue,
  isRecord,
  isNonEmptyString,
  isJsonValue,
} from '../transportValues';
import {
  type BacktestAllowedDirections,
  type BacktestRequestPayload,
  BACKTEST_ALLOWED_DIRECTIONS_SET,
  isBacktestRequestPayload,
} from './requests';
import {
  type DailyTradingSchedule,
  type DailyScheduleDraft,
  isDailyTradingSchedule,
  isDailyScheduleList,
} from './schedule';

export type ParameterAxis =
  | { mode: 'constant'; value: JsonValue }
  | { mode: 'values'; values: JsonValue[] }
  | { mode: 'range'; start: number; stop: number; step: number };

export interface ParameterDraft {
  mode: 'constant' | 'values' | 'range';
  valuesText: string;
  stringValues?: string[];
  choiceIndexes: number[];
  selectedChoiceValues?: JsonValue[];
  includeNull: boolean;
  rangeStart: number | null;
  rangeStop: number | null;
  rangeStep: number | null;
}

export interface BacktestSelectionsDraft {
  marketIds: number[];
  timeframes: string[];
  allowedDirections: BacktestAllowedDirections[];
  parameters: Record<string, ParameterDraft>;
  dailySchedule?: DailyScheduleDraft;
}

export interface BacktestPreviewRequest
  extends Omit<
    BacktestRequestPayload,
    'symbols' | 'timeframe' | 'exchange' | 'strategy'
  > {
  strategy: { strategy_id: string; strategy_version: number };
  markets: number[];
  timeframes: string[];
  parameter_axes: Record<string, ParameterAxis>;
  allowed_directions: BacktestAllowedDirections[];
  daily_schedules?: DailyTradingSchedule[];
}

export interface BacktestPreviewIssue {
  code: string;
  fields: string[];
  message: string;
}

export interface BacktestPreviewCandidate {
  candidate_ordinal: number;
  market: { symbol_id: number; symbol: string; exchange: string };
  timeframe: string;
  parameters: Record<string, JsonValue>;
  allowed_directions: BacktestAllowedDirections;
  daily_schedule?: DailyTradingSchedule;
  status: 'ready' | 'excluded';
  run_ordinal?: number;
  request?: BacktestRequestPayload;
  issues?: BacktestPreviewIssue[];
}

export interface BacktestPreview {
  max_backtest_candidate_count: number;
  normalized_selections: {
    markets: BacktestPreviewCandidate['market'][];
    timeframes: string[];
    parameters: Record<
      string,
      {
        mode: string;
        values: JsonValue[];
        range?: {
          start: number;
          stop: number;
          step: number;
        };
      }
    >;
    allowed_directions: BacktestAllowedDirections[];
    daily_schedules?: DailyTradingSchedule[];
  };
  raw_count: number;
  ready_count: number;
  excluded_count: number;
  candidates: BacktestPreviewCandidate[];
}

export function isBacktestPreview(value: unknown): value is BacktestPreview {
  if (
    !isRecord(value) ||
    !Number.isInteger(value.max_backtest_candidate_count) ||
    !Number.isInteger(value.raw_count) ||
    !Number.isInteger(value.ready_count) ||
    !Number.isInteger(value.excluded_count) ||
    !isRecord(value.normalized_selections) ||
    (value.normalized_selections.daily_schedules !== undefined &&
      !isDailyScheduleList(value.normalized_selections.daily_schedules)) ||
    !Array.isArray(value.normalized_selections.markets) ||
    !value.normalized_selections.markets.every(isBacktestMarket) ||
    !Array.isArray(value.normalized_selections.timeframes) ||
    !value.normalized_selections.timeframes.every(isNonEmptyString) ||
    !isRecord(value.normalized_selections.parameters) ||
    !Object.values(value.normalized_selections.parameters).every(
      (axis) =>
        isRecord(axis) &&
        typeof axis.mode === 'string' &&
        Array.isArray(axis.values) &&
        axis.values.length > 0 &&
        axis.values.every(isJsonValue),
    ) ||
    !Array.isArray(value.normalized_selections.allowed_directions) ||
    !value.normalized_selections.allowed_directions.every(
      (direction: unknown) =>
        typeof direction === 'string' &&
        BACKTEST_ALLOWED_DIRECTIONS_SET.has(direction),
    ) ||
    !Array.isArray(value.candidates) ||
    value.candidates.length !== value.raw_count ||
    (value.max_backtest_candidate_count as number) <= 0 ||
    (value.raw_count as number) <= 0 ||
    (value.raw_count as number) >
      (value.max_backtest_candidate_count as number) ||
    (value.ready_count as number) <= 0 ||
    (value.ready_count as number) + (value.excluded_count as number) !==
      value.raw_count
  )
    return false;
  let ready = 0;
  return (
    value.candidates.every((row: unknown, index: number) => {
      if (
        !isRecord(row) ||
        (row.daily_schedule !== undefined &&
          !isDailyTradingSchedule(row.daily_schedule)) ||
        row.candidate_ordinal !== index ||
        !isBacktestMarket(row.market) ||
        !isNonEmptyString(row.timeframe) ||
        !isRecord(row.parameters) ||
        !Object.values(row.parameters).every(isJsonValue) ||
        typeof row.allowed_directions !== 'string' ||
        !BACKTEST_ALLOWED_DIRECTIONS_SET.has(row.allowed_directions)
      )
        return false;
      if (row.status === 'ready') {
        return (
          row.run_ordinal === ready++ && isBacktestRequestPayload(row.request)
        );
      }
      return (
        row.status === 'excluded' &&
        Array.isArray(row.issues) &&
        row.issues.length > 0 &&
        row.issues.every(
          (issue: unknown) =>
            isRecord(issue) &&
            isNonEmptyString(issue.code) &&
            isNonEmptyString(issue.message) &&
            Array.isArray(issue.fields) &&
            issue.fields.every(isNonEmptyString),
        )
      );
    }) && ready === value.ready_count
  );
}

export function isBacktestMarket(
  value: unknown,
): value is BacktestPreviewCandidate['market'] {
  return (
    isRecord(value) &&
    Number.isInteger(value.symbol_id) &&
    isNonEmptyString(value.symbol) &&
    isNonEmptyString(value.exchange)
  );
}
