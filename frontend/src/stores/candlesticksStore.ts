import { defineStore } from 'pinia';
import { markRaw, ref } from 'vue';

import { fetchCandles } from '@/api/candleClient';
import {
  isCandle,
  type CandleFetchOptions,
  type CandleUpdateMessage,
  type ChartCandle,
} from '@/types/contracts';

interface CandlestickFetchOptions extends CandleFetchOptions {
  append?: boolean;
}

export const useCandlesticksStore = defineStore('candlesticks', () => {
  const type = ref<'candlestick'>('candlestick');
  const data = ref<ChartCandle[]>(markRaw([] as ChartCandle[]));

  async function fetch(
    symbol: string | null | undefined,
    timeframe: string | null | undefined,
    {
      startMs = null,
      endMs = null,
      limit = null,
      append = false,
      exchange = null,
    }: CandlestickFetchOptions = {},
  ): Promise<void> {
    if (!symbol || !timeframe) return;

    try {
      const newData = await fetchCandles(symbol, timeframe, {
        startMs,
        endMs,
        limit,
        exchange,
      });

      if (append) {
        data.value = markRaw([...newData, ...data.value]);
      } else {
        replace(newData);
      }
    } catch (err) {
      console.error('Failed to fetch candlestick data:', err);
    }
  }

  function updateCandle(candleData: CandleUpdateMessage | null | undefined): void {
    if (!isCandle(candleData)) return;

    const newCandle: ChartCandle = {
      timestamp_ms: candleData.timestamp_ms,
      time: Math.floor(candleData.timestamp_ms / 1000),
      open: candleData.open,
      high: candleData.high,
      low: candleData.low,
      close: candleData.close,
      volume: candleData.volume,
    };
    const last = data.value[data.value.length - 1];

    if (!last) {
      data.value.push(newCandle);
      return;
    }

    if (last.time === newCandle.time) {
      const isNoOp = (
        last.open === newCandle.open &&
        last.high === newCandle.high &&
        last.low === newCandle.low &&
        last.close === newCandle.close &&
        last.volume === newCandle.volume
      );
      if (!isNoOp) {
        data.value[data.value.length - 1] = newCandle;
      }
      return;
    }

    if (last.time < newCandle.time) {
      data.value.push(newCandle);
    }
  }

  function clear(): void {
    data.value = markRaw([]);
  }

  function replace(candles: readonly ChartCandle[]): void {
    data.value = markRaw([...candles]);
  }

  return {
    type,
    data,
    fetch,
    updateCandle,
    clear,
    replace,
  };
});
