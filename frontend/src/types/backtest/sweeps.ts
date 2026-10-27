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

export type SweepParameterAxis =
  | { mode: 'constant'; value: JsonValue }
  | { mode: 'values'; values: JsonValue[] }
  | { mode: 'range'; start: number; stop: number; step: number };

export interface SweepParameterDraft {
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

export interface SweepDraftState {
  isSweep: boolean;
  marketIds: number[];
  timeframes: string[];
  allowedDirections: BacktestAllowedDirections[];
  parameters: Record<string, SweepParameterDraft>;
}

export interface SweepPreviewRequest
  extends Omit<
    BacktestRequestPayload,
    'symbols' | 'timeframe' | 'exchange' | 'strategy'
  > {
  strategy: { strategy_id: string; strategy_version: number };
  markets: number[];
  timeframes: string[];
  parameter_axes: Record<string, SweepParameterAxis>;
  allowed_directions: BacktestAllowedDirections[];
}

export interface SweepPreviewIssue {
  code: string;
  fields: string[];
  message: string;
}

export interface SweepPreviewCandidate {
  candidate_ordinal: number;
  market: { symbol_id: number; symbol: string; exchange: string };
  timeframe: string;
  parameters: Record<string, JsonValue>;
  allowed_directions: BacktestAllowedDirections;
  status: 'ready' | 'excluded';
  member_ordinal?: number;
  request?: BacktestRequestPayload;
  issues?: SweepPreviewIssue[];
}

export interface SweepPreview {
  max_sweep_candidate_count: number;
  normalized_selections: {
    markets: SweepPreviewCandidate['market'][];
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
  };
  raw_count: number;
  ready_count: number;
  excluded_count: number;
  candidates: SweepPreviewCandidate[];
}

export function isSweepPreview(value: unknown): value is SweepPreview {
  if (
    !isRecord(value) ||
    !Number.isInteger(value.max_sweep_candidate_count) ||
    !Number.isInteger(value.raw_count) ||
    !Number.isInteger(value.ready_count) ||
    !Number.isInteger(value.excluded_count) ||
    !isRecord(value.normalized_selections) ||
    !Array.isArray(value.normalized_selections.markets) ||
    !value.normalized_selections.markets.every(isSweepMarket) ||
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
    (value.max_sweep_candidate_count as number) <= 0 ||
    (value.raw_count as number) <= 0 ||
    (value.raw_count as number) > (value.max_sweep_candidate_count as number) ||
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
        row.candidate_ordinal !== index ||
        !isSweepMarket(row.market) ||
        !isNonEmptyString(row.timeframe) ||
        !isRecord(row.parameters) ||
        !Object.values(row.parameters).every(isJsonValue) ||
        typeof row.allowed_directions !== 'string' ||
        !BACKTEST_ALLOWED_DIRECTIONS_SET.has(row.allowed_directions)
      )
        return false;
      if (row.status === 'ready') {
        return (
          row.member_ordinal === ready++ &&
          isBacktestRequestPayload(row.request)
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

export function isSweepMarket(
  value: unknown,
): value is SweepPreviewCandidate['market'] {
  return (
    isRecord(value) &&
    Number.isInteger(value.symbol_id) &&
    isNonEmptyString(value.symbol) &&
    isNonEmptyString(value.exchange)
  );
}
