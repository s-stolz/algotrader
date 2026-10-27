import {
  isNullableNumber,
  isNullableString,
  isJsonObject,
} from '../transportValues';

export function isEpochMs(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) >= 0;
}

export function isOrdinal(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) >= 0;
}

export function isOptionalNullableNumber(
  value: Record<string, unknown>,
  key: string,
): boolean {
  return (
    !(key in value) || value[key] === undefined || isNullableNumber(value[key])
  );
}

export function isOptionalNullableString(
  value: Record<string, unknown>,
  key: string,
): boolean {
  return (
    !(key in value) || value[key] === undefined || isNullableString(value[key])
  );
}

export function isOptionalNullableJsonObject(
  value: Record<string, unknown>,
  key: string,
): boolean {
  return (
    !(key in value) ||
    value[key] === undefined ||
    value[key] === null ||
    isJsonObject(value[key])
  );
}
