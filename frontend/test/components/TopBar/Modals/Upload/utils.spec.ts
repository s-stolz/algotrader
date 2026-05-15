import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  getColumnMapping,
  getFieldToIndexMapping,
  getHeaderLine,
  getSeparator,
  parseCsvToCandles,
  uploadCandlesInBatches,
  validateRequiredFields,
} from '@/components/TopBar/Modals/Upload/utils';

const csvFile = (text: string) => new File([text], 'candles.csv', { type: 'text/csv' });

describe('upload CSV utilities', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('detects separators, headers, and common column mappings', () => {
    const text = 'Date;Time;Open;High;Low;Close;Volume\n2026-01-01;00:00;1;2;0.5;1.5;100';
    const separator = getSeparator(text);
    const header = getHeaderLine(text, separator);

    expect(separator).toBe(';');
    expect(header).toEqual(['Date', 'Time', 'Open', 'High', 'Low', 'Close', 'Volume']);
    expect(getColumnMapping(header)).toEqual({
      0: 'date',
      1: 'time',
      2: 'open',
      3: 'high',
      4: 'low',
      5: 'close',
      6: 'volume',
    });
  });

  it('validates timestamp or date-time plus OHLCV requirements', () => {
    expect(() => validateRequiredFields({
      timestamp: 0,
      open: 1,
      high: 2,
      low: 3,
      close: 4,
      volume: 5,
    })).not.toThrow();

    expect(() => validateRequiredFields({
      date: 0,
      time: 1,
      open: 2,
      high: 3,
      low: 4,
      close: 5,
      volume: 6,
    })).not.toThrow();

    expect(() => validateRequiredFields({
      open: 0,
      high: 1,
      low: 2,
      close: 3,
      volume: 4,
    })).toThrow('Missing timestamp field');
    expect(() => validateRequiredFields({
      timestamp: 0,
      high: 1,
      low: 2,
      close: 3,
      volume: 4,
    })).toThrow('Missing required field: open');
  });

  it('parses valid rows, rejects invalid rows, and reports progress', async () => {
    const file = csvFile([
      'Timestamp,Open,High,Low,Close,Volume',
      '2026-01-01T00:00:00Z,1,2,0.5,1.5,100',
      '2026-01-01T00:01:00Z,1,0.75,0.5,1.5,100',
      '2026-01-01T00:02:00Z,1.5,2.5,1,2,150',
    ].join('\n'));
    const progress = vi.fn();

    await expect(parseCsvToCandles(file, ',', {
      0: 'timestamp',
      1: 'open',
      2: 'high',
      3: 'low',
      4: 'close',
      5: 'volume',
    }, progress)).resolves.toEqual([
      {
        timestamp_ms: Date.parse('2026-01-01T00:00:00Z'),
        open: 1,
        high: 2,
        low: 0.5,
        close: 1.5,
        volume: 100,
      },
      {
        timestamp_ms: Date.parse('2026-01-01T00:02:00Z'),
        open: 1.5,
        high: 2.5,
        low: 1,
        close: 2,
        volume: 150,
      },
    ]);

    expect(progress).toHaveBeenCalledWith(100, 2);
  });

  it('parses date plus time mappings', async () => {
    const candles = await parseCsvToCandles(csvFile([
      'Date,Time,Open,High,Low,Close,Volume',
      '2026-01-01,00:00:00,1,2,0.5,1.5,100',
    ].join('\n')), ',', {
      0: 'date',
      1: 'time',
      2: 'open',
      3: 'high',
      4: 'low',
      5: 'close',
      6: 'volume',
    });

    expect(candles).toEqual([{
      timestamp_ms: Date.parse('2026-01-01 00:00:00'),
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      volume: 100,
    }]);
  });

  it('uploads candles in batches while preserving symbol and exchange payloads', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({
        status: 'ok',
        added_candles: 1,
        total_candles: 1,
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ));
    const progress = vi.fn();
    const candles = Array.from({ length: 20_001 }, (_, index) => ({
      timestamp_ms: index + 1,
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      volume: 100,
    }));

    await uploadCandlesInBatches('EURUSD', candles, 'FX', progress);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(JSON.parse(fetchMock.mock.calls[0][1]?.body as string)).toMatchObject({
      symbol: 'EURUSD',
      exchange: 'FX',
      candles: expect.arrayContaining([expect.objectContaining({ timestamp_ms: 1 })]),
    });
    expect(JSON.parse(fetchMock.mock.calls[1][1]?.body as string)).toMatchObject({
      symbol: 'EURUSD',
      exchange: 'FX',
      candles: [expect.objectContaining({ timestamp_ms: 20_001 })],
    });
    expect(progress).toHaveBeenLastCalledWith(100, 20_001);
  });

  it('derives field-to-index mappings from preview column mappings', () => {
    expect(getFieldToIndexMapping({
      0: 'timestamp',
      1: 'open',
      2: '',
    })).toEqual({
      timestamp: 0,
      open: 1,
    });
  });
});
