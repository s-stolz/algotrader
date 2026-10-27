import type { SelectOption } from 'naive-ui';
import type {
  StrategyCatalogEntry,
  StrategyParameterSchema,
} from '@/types/backtesterContracts';

export function parameterIssue(
  parameter: StrategyParameterSchema,
  value: unknown,
): string | null {
  if (value === undefined)
    return parameter.required ? 'This parameter is required.' : null;
  if (value === null) return parameter.nullable ? null : 'null is unavailable';
  const correctType =
    parameter.type === 'bool'
      ? typeof value === 'boolean'
      : parameter.type === 'str'
        ? typeof value === 'string'
        : typeof value === 'number' &&
          Number.isFinite(value) &&
          (parameter.type !== 'int' || Number.isInteger(value));
  if (!correctType) return `expected ${parameter.type}`;
  if (
    parameter.choices &&
    !parameter.choices.includes(value as number | string)
  ) {
    return `${JSON.stringify(value)} is not a current choice`;
  }
  if (typeof value === 'number') {
    if (
      parameter.minimum !== undefined &&
      (parameter.exclusive_minimum
        ? value <= parameter.minimum
        : value < parameter.minimum)
    )
      return 'below current minimum';
    if (
      parameter.maximum !== undefined &&
      (parameter.exclusive_maximum
        ? value >= parameter.maximum
        : value > parameter.maximum)
    )
      return 'above current maximum';
  }
  return null;
}

export function parameterModeOptions(
  parameter: StrategyParameterSchema,
): SelectOption[] {
  const modes: SelectOption[] = [
    { label: 'Constant', value: 'constant' },
    { label: 'Values', value: 'values' },
  ];
  if (
    (parameter.type === 'int' || parameter.type === 'float') &&
    !parameter.choices
  ) {
    modes.push({ label: 'Range', value: 'range' });
  }
  return modes;
}

export function defaults(
  strategy: StrategyCatalogEntry,
): Record<string, null | boolean | number | string> {
  return Object.fromEntries(
    strategy.parameters
      .filter((parameter) => 'default' in parameter)
      .map((parameter) => [parameter.name, parameter.default]),
  ) as Record<string, null | boolean | number | string>;
}

export function parameterOptions(
  parameter: StrategyParameterSchema,
): SelectOption[] {
  return choiceValues(parameter).map((value, index) => ({
    label: value === null ? 'Null' : String(value),
    value: index,
  }));
}

export function choiceValues(
  parameter: StrategyParameterSchema,
): (null | boolean | number | string)[] {
  const values =
    parameter.type === 'bool' ? [true, false] : (parameter.choices ?? []);
  return parameter.nullable ? [...values, null] : values;
}

export function dateValue(timestamp: number): string {
  return Number.isFinite(timestamp)
    ? new Date(timestamp).toISOString().slice(0, 10)
    : '';
}
