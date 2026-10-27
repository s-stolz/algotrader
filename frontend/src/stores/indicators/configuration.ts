import type { IndicatorInfo, JsonValue } from '@/types/contracts';
import type {
  IndicatorParameterEntry,
  IndicatorParameterMap,
  IndicatorParameterUpdate,
  IndicatorParameterValues,
  IndicatorStyles,
} from './types';

export function isParameterEntry(
  value: JsonValue | IndicatorParameterEntry,
): value is IndicatorParameterEntry {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function createParameterMap(
  info: IndicatorInfo,
  providedParameters: IndicatorParameterUpdate = {},
): IndicatorParameterMap {
  const finalParameters: IndicatorParameterMap = {};

  for (const [key, provided] of Object.entries(providedParameters)) {
    finalParameters[key] = isParameterEntry(provided)
      ? { ...provided }
      : { value: provided };
  }

  for (const [key, paramInfo] of Object.entries(info.parameters)) {
    const existing = finalParameters[key];

    if (!existing) {
      finalParameters[key] = {
        ...paramInfo,
        value: paramInfo.default,
      };
      continue;
    }

    finalParameters[key] = {
      ...paramInfo,
      ...existing,
    };

    if (finalParameters[key].value === undefined) {
      finalParameters[key].value = finalParameters[key].default;
    }
  }

  return finalParameters;
}

export function createStyles(
  outputs: IndicatorInfo['outputs'],
): IndicatorStyles {
  const styles: IndicatorStyles = {};

  for (const [outputKey, output] of Object.entries(outputs)) {
    if (outputKey !== 'timestamp') {
      styles[outputKey] = output.plotOptions ? { ...output.plotOptions } : {};
    }
  }

  return styles;
}

export function extractParameterValues(
  parameters: IndicatorParameterMap,
): IndicatorParameterValues {
  const out: IndicatorParameterValues = {};

  for (const [key, parameter] of Object.entries(parameters)) {
    const value =
      parameter.value !== undefined ? parameter.value : parameter.default;
    if (value !== undefined) {
      out[key] = value;
    }
  }

  return out;
}

export function applyParameterUpdates(
  parameters: IndicatorParameterMap,
  newParameters: IndicatorParameterUpdate,
): IndicatorParameterMap {
  for (const [key, paramVal] of Object.entries(newParameters)) {
    const parameter = parameters[key];
    if (!parameter) continue;

    if (isParameterEntry(paramVal)) {
      if ('value' in paramVal) {
        parameter.value = paramVal.value;
      }
    } else {
      parameter.value = paramVal;
    }
  }

  return parameters;
}
