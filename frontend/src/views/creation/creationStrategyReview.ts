import type {
  StrategyCatalogEntry,
  StrategyParameterSchema,
} from '@/types/backtesterContracts';
import type { ReuseSource } from '../backtestReuse';
import type { DraftRequest } from './creationRequest';

export interface ParameterChange {
  parameter: string;
  change: string;
  saved?: string;
  current?: string;
}

function displayValue(value: unknown): string {
  return value === undefined ? 'Not set' : JSON.stringify(value);
}

export function parameterChanges(
  source: ReuseSource | null,
  selected: StrategyCatalogEntry | undefined,
  draft: DraftRequest,
  needsReview: boolean,
): ParameterChange[] {
  if (!source || !selected || source.strategyId !== selected.strategy_id)
    return [];
  const old = source.historicalMetadata;
  const oldNames =
    old?.parameters.map((parameter) => parameter.name) ??
    Object.keys(draft.strategy.parameters);
  const newNames = selected.parameters.map((parameter) => parameter.name);
  const changes: ParameterChange[] = [
    ...newNames
      .filter((name) => !oldNames.includes(name))
      .map((parameter) => ({
        parameter,
        change: 'Added',
      })),
    ...oldNames
      .filter((name) => !newNames.includes(name))
      .map((parameter) => ({
        parameter,
        change: 'Removed',
      })),
  ];
  if (old) {
    for (const parameter of selected.parameters) {
      const previous = old.parameters.find(
        (item) => item.name === parameter.name,
      );
      if (!previous || sameParameterSchema(previous, parameter)) continue;
      const fields = [
        ['default', 'Default'],
        ['choices', 'Choices'],
        ['type', 'Type'],
      ] as const;
      let described = false;
      for (const [key, change] of fields) {
        if (JSON.stringify(previous[key]) === JSON.stringify(parameter[key]))
          continue;
        changes.push({
          parameter: parameter.name,
          change,
          saved: displayValue(previous[key]),
          current: displayValue(parameter[key]),
        });
        described = true;
      }
      if (!described)
        changes.push({ parameter: parameter.name, change: 'Schema changed' });
    }
  }
  if (!old && needsReview) {
    for (const parameter of selected.parameters) {
      const saved = draft.strategy.parameters[parameter.name];
      if (
        saved !== undefined &&
        'default' in parameter &&
        JSON.stringify(saved) !== JSON.stringify(parameter.default)
      ) {
        changes.push({
          parameter: parameter.name,
          change: 'Value / default',
          saved: displayValue(saved),
          current: displayValue(parameter.default),
        });
      }
    }
  }
  return changes;
}

function sameParameterSchema(
  left: StrategyParameterSchema,
  right: StrategyParameterSchema,
): boolean {
  const keys = new Set([...Object.keys(left), ...Object.keys(right)]);
  return [...keys].every(
    (key) =>
      JSON.stringify(left[key as keyof StrategyParameterSchema]) ===
      JSON.stringify(right[key as keyof StrategyParameterSchema]),
  );
}
