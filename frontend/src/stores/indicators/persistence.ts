import { isJsonObject } from '@/types/transportValues';
import { ref, watch } from 'vue';
import { fetchAvailableIndicators } from '@/api/indicatorClient';
import { isIndicatorInfo, isRecord } from '@/types/contracts';
import type { IndicatorInfo } from '@/types/contracts';
import {
  getStoredState,
  setStoredState,
  STORAGE_KEYS,
} from '@/utils/localStorage';
import { createIndicator } from './creation';
import { extractParameterValues } from './configuration';
import type {
  IndicatorParameterValues,
  IndicatorStyles,
  StoreIndicator,
} from './types';

interface SavedIndicator {
  info: IndicatorInfo;
  parameters: IndicatorParameterValues;
  styles: IndicatorStyles;
  paneIndex: number;
}

export function isIndicatorStyles(value: unknown): value is IndicatorStyles {
  return isRecord(value) && Object.values(value).every(isJsonObject);
}

function isSavedIndicator(value: unknown): value is SavedIndicator {
  return (
    isRecord(value) &&
    isIndicatorInfo(value.info) &&
    isJsonObject(value.parameters) &&
    isIndicatorStyles(value.styles) &&
    typeof value.paneIndex === 'number' &&
    Number.isInteger(value.paneIndex) &&
    value.paneIndex >= 0
  );
}

// Observe configuration only: live points, requests, and DOM state never reach storage.
export function createIndicatorPersistence(
  indicators: Map<string, StoreIndicator>,
  setPaneCount: (count: number) => void,
) {
  let started = false;
  const ready = ref(false);
  let pending: SavedIndicator[] = [];
  watch(
    () =>
      ready.value &&
      Array.from(indicators.values())
        .filter((item) => !item.ownerRunId)
        .map((item) => ({
          info: item.info,
          parameters: extractParameterValues(item.parameters),
          styles: item.styles,
          paneIndex: item.paneIndex,
        })),
    (items) =>
      items &&
      setStoredState(STORAGE_KEYS.INDICATORS, {
        version: 1,
        items: [...pending, ...items],
      }),
    { deep: true, immediate: true },
  );
  return async function restore() {
    if (started) return;
    started = true;
    const stored = getStoredState<unknown>(STORAGE_KEYS.INDICATORS);

    if (
      isRecord(stored) &&
      stored.version === 1 &&
      Array.isArray(stored.items)
    ) {
      pending = stored.items.filter(isSavedIndicator);
      if (pending.length !== stored.items.length)
        console.error('Discarded invalid saved indicators.');
    }
    if (pending.length) {
      try {
        const catalog = await fetchAvailableIndicators();
        for (const saved of pending) {
          const match = catalog.find(
            (item) => item.indicator_id === saved.info.indicator_id,
          );
          if (!match) {
            console.error(
              'Saved indicator is unavailable:',
              saved.info.indicator_id,
            );
            continue;
          }
          const id = crypto.randomUUID();
          const indicator = createIndicator(
            id,
            { ...saved.info, id: match.id },
            [],
            match.id,
            saved.paneIndex,
            saved.parameters,
          );
          indicator.styles = saved.styles;
          indicators.set(id, indicator);
        }
        pending = [];
        setPaneCount(
          Math.max(
            1,
            ...Array.from(indicators.values(), (item) => item.paneIndex + 1),
          ),
        );
      } catch (error) {
        console.error('Failed to restore indicators:', error);
      }
    }
    ready.value = true;
  };
}
