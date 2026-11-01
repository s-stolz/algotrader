import {
  isJsonObject,
  isRecord,
  isNonEmptyString,
  type JsonObject,
} from '../transportValues';

export interface SavedChartIndicator {
  indicator_id: string;
  parameters: JsonObject;
}

export function readChartIndicators(
  diagnostics: JsonObject | null | undefined,
): SavedChartIndicator[] | null {
  const snapshot = diagnostics?.chart_indicators;
  if (snapshot === undefined) return null;
  if (
    !isRecord(snapshot) ||
    snapshot.schema_version !== 1 ||
    !Array.isArray(snapshot.items)
  ) {
    throw new Error('Saved indicator configuration is unsupported.');
  }
  return snapshot.items.map((item) => {
    if (
      !isRecord(item) ||
      !isNonEmptyString(item.indicator_id) ||
      !isJsonObject(item.parameters)
    ) {
      throw new Error('Saved indicator configuration is invalid.');
    }
    return {
      indicator_id: item.indicator_id,
      parameters: { ...item.parameters },
    };
  });
}
