import { uploadCandleBatch } from '@/api/candleClient';
import {
  type Candle,
  type UploadColumnField,
  type UploadColumnMapping,
  type UploadFieldToIndexMapping,
  type UploadProgressCallback,
  isCandle,
} from '@/types/contracts';

const CHUNK_SIZE = 64 * 1024 * 1024;
const BATCH_SIZE = 20000;

type TimestampReader = (cols: string[]) => number;

export function getHeaderLine(csvText: string, separator: string): string[] {
  const lines = csvText.trim().split('\n');
  if (lines.length === 0 || !lines[0]) return [];

  return lines[0].split(separator).map((col) => col.trim());
}

export function getSeparator(
  csvText: string,
  separatorOptions: string[] = [',', '\t', ';', '|'],
): string {
  const lines = csvText.trim().split('\n');

  const firstLine = lines.find((line) => line.trim());
  if (!firstLine) return ',';

  let bestSeparator = ',';
  let maxColumns = 0;

  for (const separator of separatorOptions) {
    const columns = firstLine.split(separator);
    if (columns.length > maxColumns) {
      maxColumns = columns.length;
      bestSeparator = separator;
    }
  }

  return bestSeparator;
}

export function getColumnMapping(headerLine: string[]): UploadColumnMapping {
  const mapping: UploadColumnMapping = {};

  for (let index = 0; index < headerLine.length; index++) {
    const column = headerLine[index];
    const lowerCaseColumn = column.toLowerCase();

    if (lowerCaseColumn.includes('timestamp') || lowerCaseColumn.includes('datetime')) {
      mapping[index] = 'timestamp';
    } else if (lowerCaseColumn.includes('date') && !lowerCaseColumn.includes('time')) {
      mapping[index] = 'date';
    } else if (lowerCaseColumn.includes('time') && !lowerCaseColumn.includes('date')) {
      mapping[index] = 'time';
    } else if (lowerCaseColumn.includes('open')) {
      mapping[index] = 'open';
    } else if (lowerCaseColumn.includes('high')) {
      mapping[index] = 'high';
    } else if (lowerCaseColumn.includes('low')) {
      mapping[index] = 'low';
    } else if (lowerCaseColumn.includes('close')) {
      mapping[index] = 'close';
    } else if (lowerCaseColumn.includes('volume') || lowerCaseColumn.includes('vol')) {
      mapping[index] = 'volume';
    }
  }

  return mapping;
}

export async function parseCsvToCandles(
  file: File,
  separator: string,
  columnMapping: UploadColumnMapping,
  onProgress: UploadProgressCallback | null = null,
): Promise<Candle[]> {
  const fieldToIndex = getFieldToIndexMapping(columnMapping);
  validateRequiredFields(fieldToIndex);
  const getTimestamp = getTimestampFunction(fieldToIndex);

  let allCandles: Candle[] = [];
  let position = 0;
  let rowCount = 0;
  let partialLine = '';
  let isFirstChunk = true;

  while (position < file.size) {
    const end = Math.min(position + CHUNK_SIZE, file.size);
    const chunkText = await readFileChunk(file, position, end);

    const fullText = partialLine + chunkText;
    const lines = fullText.split('\n');

    if (end < file.size) {
      partialLine = lines.pop() ?? '';
    } else {
      partialLine = '';
    }

    const startIndex = isFirstChunk ? 1 : 0;
    isFirstChunk = false;

    const batchCandles: Candle[] = [];

    for (let i = startIndex; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      const cols = line.split(separator).map((col) => col.trim());
      const candle = createCandleFromRow(cols, fieldToIndex, getTimestamp, rowCount);

      if (candle) {
        batchCandles.push(candle);
        rowCount++;
      }
    }

    allCandles = allCandles.concat(batchCandles);
    position = end;

    if (onProgress) {
      const progress = (position / file.size) * 100;
      onProgress(progress, rowCount);
    }
  }

  return allCandles;
}

export function getFieldToIndexMapping(columnMapping: UploadColumnMapping): UploadFieldToIndexMapping {
  const fieldToIndex: UploadFieldToIndexMapping = {};

  Object.entries(columnMapping).forEach(([index, field]) => {
    if (field) {
      fieldToIndex[field] = Number.parseInt(index, 10);
    }
  });

  return fieldToIndex;
}

export function validateRequiredFields(fieldToIndex: UploadFieldToIndexMapping): void {
  const hasTimestamp = typeof fieldToIndex.timestamp === 'number';
  const hasDateAndTime = typeof fieldToIndex.date === 'number' && typeof fieldToIndex.time === 'number';

  if (!hasTimestamp && !hasDateAndTime) {
    throw new Error(
      'Missing timestamp field. Either map a "Timestamp" column or both "Date" and "Time" columns.',
    );
  }

  const requiredFields: UploadColumnField[] = ['open', 'high', 'low', 'close', 'volume'];
  for (const field of requiredFields) {
    if (typeof fieldToIndex[field] !== 'number') {
      throw new Error(`Missing required field: ${field}`);
    }
  }
}

function getTimestampFunction(fieldToIndex: UploadFieldToIndexMapping): TimestampReader {
  const hasTimestamp = typeof fieldToIndex.timestamp === 'number';
  const hasDateAndTime = typeof fieldToIndex.date === 'number' && typeof fieldToIndex.time === 'number';

  if (hasTimestamp) {
    return (cols) => getTimestampFromTimestamp(cols, fieldToIndex);
  }

  if (hasDateAndTime) {
    return (cols) => getTimestampFromDateAndTime(cols, fieldToIndex);
  }

  throw new Error(
    'Missing timestamp field. Either map a "Timestamp" column or both "Date" and "Time" columns.',
  );
}

function getMappedColumn(
  cols: string[],
  fieldToIndex: UploadFieldToIndexMapping,
  field: UploadColumnField,
): string {
  const index = fieldToIndex[field];
  return typeof index === 'number' ? cols[index] ?? '' : '';
}

function getTimestampFromTimestamp(cols: string[], fieldToIndex: UploadFieldToIndexMapping): number {
  const date = new Date(getMappedColumn(cols, fieldToIndex, 'timestamp'));
  return date.getTime();
}

function getTimestampFromDateAndTime(cols: string[], fieldToIndex: UploadFieldToIndexMapping): number {
  const dateStr = getMappedColumn(cols, fieldToIndex, 'date').trim();
  const timeStr = getMappedColumn(cols, fieldToIndex, 'time').trim();

  const combinedDateTime = `${dateStr} ${timeStr}`;
  const date = new Date(combinedDateTime);

  return date.getTime();
}

export function readFileChunk(file: File, start: number, end: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result);
        return;
      }

      reject(new Error('Expected text result while reading CSV chunk'));
    };
    reader.onerror = () => reject(reader.error ?? new Error('Failed to read CSV chunk'));
    reader.readAsText(file.slice(start, end));
  });
}

function createCandleFromRow(
  cols: string[],
  fieldToIndex: UploadFieldToIndexMapping,
  getTimestamp: TimestampReader,
  rowCount: number,
): Candle | null {
  try {
    const timestamp = getTimestamp(cols);

    const candle = {
      timestamp_ms: timestamp,
      open: Number.parseFloat(getMappedColumn(cols, fieldToIndex, 'open')),
      high: Number.parseFloat(getMappedColumn(cols, fieldToIndex, 'high')),
      low: Number.parseFloat(getMappedColumn(cols, fieldToIndex, 'low')),
      close: Number.parseFloat(getMappedColumn(cols, fieldToIndex, 'close')),
      volume: Number.parseFloat(getMappedColumn(cols, fieldToIndex, 'volume')),
    };

    if (isCandle(candle)) {
      return candle;
    }
    return null;
  } catch (parseError) {
    console.warn(`Error parsing row ${rowCount + 1}:`, parseError);
    return null;
  }
}

export async function uploadCandlesInBatches(
  symbol: string,
  candles: Candle[],
  exchange: string | null,
  onProgress?: UploadProgressCallback,
): Promise<void> {
  const batches: Candle[][] = [];

  for (let i = 0; i < candles.length; i += BATCH_SIZE) {
    batches.push(candles.slice(i, i + BATCH_SIZE));
  }

  for (let i = 0; i < batches.length; i++) {
    const payload = {
      symbol,
      candles: batches[i],
      ...(exchange ? { exchange } : {}),
    };

    await uploadCandleBatch(payload);

    if (onProgress) {
      const progress = ((i + 1) / batches.length) * 100;
      onProgress(progress, (i + 1) * BATCH_SIZE);
    }
  }
}
