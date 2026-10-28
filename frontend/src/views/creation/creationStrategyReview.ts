import type {
  StrategyCatalogEntry,
  StrategyParameterSchema,
} from '@/types/backtesterContracts';
import type { ReuseSource } from '../backtestReuse';
import type { DraftRequest } from './creationRequest';

export function parameterChanges(
  source: ReuseSource | null,
  selected: StrategyCatalogEntry | undefined,
  draft: DraftRequest,
  issues: string[],
  needsReview: boolean,
): string[] {
  if (!source || !selected) return [];
  const old = source.historicalMetadata;
  const oldNames =
    old?.parameters.map((parameter) => parameter.name) ??
    Object.keys(draft.strategy.parameters);
  const newNames = selected.parameters.map((parameter) => parameter.name);
  const changes = [
    ...newNames
      .filter((name) => !oldNames.includes(name))
      .map((name) => `New parameter: ${name}`),
    ...oldNames
      .filter((name) => !newNames.includes(name))
      .map((name) => `Removed parameter: ${name}`),
    ...issues.map((issue) => `Invalid copied value: ${issue}`),
  ];
  if (old)
    for (const parameter of selected.parameters) {
      const previous = old.parameters.find(
        (item) => item.name === parameter.name,
      );
      if (previous && !sameParameterSchema(previous, parameter)) {
        let described = false;
        if (
          JSON.stringify(previous.default) !== JSON.stringify(parameter.default)
        ) {
          changes.push(
            `${parameter.name} default changed: ${JSON.stringify(previous.default)} → ` +
              JSON.stringify(parameter.default),
          );
          described = true;
        }
        if (
          JSON.stringify(previous.choices) !== JSON.stringify(parameter.choices)
        ) {
          changes.push(
            `${parameter.name} choices changed: ${JSON.stringify(previous.choices ?? [])} → ` +
              JSON.stringify(parameter.choices ?? []),
          );
          described = true;
        }
        if (previous.type !== parameter.type) {
          changes.push(
            `${parameter.name} type changed: ${previous.type} → ${parameter.type}`,
          );
          described = true;
        }
        if (!described)
          changes.push(`Changed parameter contract: ${parameter.name}`);
      }
    }
  if (!old && needsReview)
    for (const parameter of selected.parameters) {
      const saved = draft.strategy.parameters[parameter.name];
      if (
        saved !== undefined &&
        'default' in parameter &&
        JSON.stringify(saved) !== JSON.stringify(parameter.default)
      ) {
        changes.push(
          `${parameter.name}: saved value ${JSON.stringify(saved)}; ` +
            `current default ${JSON.stringify(parameter.default)}.`,
        );
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
