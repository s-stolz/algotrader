import { expect, it } from 'vitest';
import {
  isHistoryEvent,
  isMarketCoverage,
} from '@/types/historyDownloadContracts';

it('validates market-scoped invalidations and upstream connection events', () => {
  expect(
    isHistoryEvent({
      type: 'historyDownloadChanged',
      market_id: 7,
      job_id: 'job',
      revision: 2,
    }),
  ).toBe(true);
  expect(
    isHistoryEvent({
      type: 'historyDownloadsConnection',
      market_id: 7,
      connected: true,
    }),
  ).toBe(true);
  expect(
    isHistoryEvent({
      type: 'historyDownloadsConnection',
      market_id: 7,
      connected: 'true',
    }),
  ).toBe(false);
  expect(
    isHistoryEvent({
      type: 'historyDownloadChanged',
      market_id: 0,
      job_id: 'job',
      revision: 2,
    }),
  ).toBe(false);
  expect(
    isHistoryEvent({
      type: 'historyDownloadChanged',
      market_id: 7,
      job_id: 'job',
      revision: -1,
    }),
  ).toBe(false);
});
it('accepts empty coverage without inventing a date or completeness guarantee', () => {
  expect(
    isMarketCoverage({
      market_id: 7,
      oldest_timestamp_ms: null,
      latest_timestamp_ms: null,
      candle_count: 0,
    }),
  ).toBe(true);
  expect(
    isMarketCoverage({
      market_id: 7,
      oldest_timestamp_ms: null,
      latest_timestamp_ms: null,
      candle_count: -1,
    }),
  ).toBe(false);
});
