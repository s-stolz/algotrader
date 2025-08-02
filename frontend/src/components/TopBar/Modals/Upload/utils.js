export function getHeaderLine(csvText, separator) {
  const lines = csvText.trim().split("\n");
  if (lines.length === 0) return [];

  return lines[0].split(separator).map((col) => col.trim());
}

export function getSeparator(csvText, separatorOptions = [",", "\t", ";", "|"]) {
  const lines = csvText.trim().split("\n");

  const firstLine = lines.find((line) => line.trim());
  if (!firstLine) return ",";

  let bestSeparator = ",";
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

export function getColumnMapping(headerLine) {
  const mapping = {};

  for (let index = 0; index < headerLine.length; index++) {
    const column = headerLine[index];
    const lowerCaseColumn = column.toLowerCase();

    if (lowerCaseColumn.includes("timestamp") || lowerCaseColumn.includes("datetime")) {
      mapping[index] = "timestamp";
    } else if (lowerCaseColumn.includes("date") && !lowerCaseColumn.includes("time")) {
      mapping[index] = "date";
    } else if (lowerCaseColumn.includes("time") && !lowerCaseColumn.includes("date")) {
      mapping[index] = "time";
    } else if (lowerCaseColumn.includes("open")) {
      mapping[index] = "open";
    } else if (lowerCaseColumn.includes("high")) {
      mapping[index] = "high";
    } else if (lowerCaseColumn.includes("low")) {
      mapping[index] = "low";
    } else if (lowerCaseColumn.includes("close")) {
      mapping[index] = "close";
    } else if (lowerCaseColumn.includes("volume") || lowerCaseColumn.includes("vol")) {
      mapping[index] = "volume";
    }
  }

  return mapping;
}

export async function parseCsvToCandles(file, separator, columnMapping, onProgress = null) {
  const CHUNK_SIZE = 64 * 1024 * 1024;

  const fieldToIndex = getFieldToIndexMapping(columnMapping);
  validateRequiredFields(fieldToIndex);
  const getTimestamp = getTimestampFunction(fieldToIndex);

  let allCandles = [];
  let position = 0;
  let rowCount = 0;
  let partialLine = '';
  let isFirstChunk = true;

  while (position < file.size) {
    const end = Math.min(position + CHUNK_SIZE, file.size);
    const chunkText = await readFileChunk(file, position, end);

    let fullText = partialLine + chunkText;
    const lines = fullText.split('\n');

    if (end < file.size) {
      partialLine = lines.pop();
    } else {
      partialLine = '';
    }

    // Skip header line on first chunk
    const startIndex = isFirstChunk ? 1 : 0;
    isFirstChunk = false;

    const batchCandles = [];

    for (let i = startIndex; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      const cols = line.split(separator).map(col => col.trim());
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

export function getFieldToIndexMapping(columnMapping) {
  const fieldToIndex = {};
  Object.entries(columnMapping).forEach(([index, field]) => {
    if (field) fieldToIndex[field] = parseInt(index);
  });
  return fieldToIndex;
}

export function validateRequiredFields(fieldToIndex) {
  const hasTimestamp = "timestamp" in fieldToIndex;
  const hasDateAndTime = "date" in fieldToIndex && "time" in fieldToIndex;

  if (!hasTimestamp && !hasDateAndTime) {
    throw new Error(
      'Missing timestamp field. Either map a "Timestamp" column or both "Date" and "Time" columns.',
    );
  }

  const requiredFields = ["open", "high", "low", "close", "volume"];
  for (const field of requiredFields) {
    if (!(field in fieldToIndex)) {
      throw new Error(`Missing required field: ${field}`);
    }
  }
}

function getTimestampFunction(fieldToIndex) {
  const hasTimestamp = "timestamp" in fieldToIndex;
  const hasDateAndTime = "date" in fieldToIndex && "time" in fieldToIndex;

  if (hasTimestamp) {
    return (cols) => getTimestampFromTimestamp(cols, fieldToIndex);
  } else if (hasDateAndTime) {
    return (cols) => getTimestampFromDateAndTime(cols, fieldToIndex);
  } else {
    throw new Error(
      'Missing timestamp field. Either map a "Timestamp" column or both "Date" and "Time" columns.',
    );
  }
}

function getTimestampFromTimestamp(cols, fieldToIndex) {
  const date = new Date(cols[fieldToIndex.timestamp]);
  return date.toISOString().replace("Z", "");
}

function getTimestampFromDateAndTime(cols, fieldToIndex) {
  const dateStr = cols[fieldToIndex.date].trim();
  const timeStr = cols[fieldToIndex.time].trim();

  const combinedDateTime = `${dateStr} ${timeStr}`;
  const date = new Date(combinedDateTime);

  return date.toISOString().replace("Z", "");
}

export function readFileChunk(file, start, end) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.onerror = (e) => reject(e);
    reader.readAsText(file.slice(start, end));
  });
}

function createCandleFromRow(cols, fieldToIndex, getTimestamp, rowCount) {
  try {
    const timestamp = getTimestamp(cols);

    const candle = {
      timestamp: timestamp,
      open: parseFloat(cols[fieldToIndex.open]),
      high: parseFloat(cols[fieldToIndex.high]),
      low: parseFloat(cols[fieldToIndex.low]),
      close: parseFloat(cols[fieldToIndex.close]),
      volume: parseFloat(cols[fieldToIndex.volume]),
    };

    if (isValidCandle(candle, timestamp)) {
      return candle;
    }
    return null;
  } catch (parseError) {
    console.warn(`Error parsing row ${rowCount + 1}:`, parseError);
    return null;
  }
}

function isValidCandle(candle, timestamp) {
  if (
    !timestamp ||
    timestamp === "Invalid Date" ||
    isNaN(candle.open) ||
    isNaN(candle.high) ||
    isNaN(candle.low) ||
    isNaN(candle.close) ||
    isNaN(candle.volume) ||
    candle.high < Math.max(candle.low, candle.open, candle.close) ||
    candle.low > Math.min(candle.open, candle.close)
  ) {
    return false;
  }
  return true;
}

export async function uploadCandlesInBatches(symbolId, candles, onProgress) {
  const BATCH_SIZE = 20000;
  const batches = [];

  for (let i = 0; i < candles.length; i += BATCH_SIZE) {
    batches.push(candles.slice(i, i + BATCH_SIZE));
  }

  for (let i = 0; i < batches.length; i++) {
    const batch = batches[i];
    const payload = {
      symbol_id: symbolId,
      candles: batch,
    };

    const response = await fetch("/api/data-accessor/candles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Failed to upload batch ${i + 1}: ${response.statusText}`);
    }

    if (onProgress) {
      const progress = ((i + 1) / batches.length) * 100;
      onProgress(progress, (i + 1) * BATCH_SIZE);
    }
  }
}