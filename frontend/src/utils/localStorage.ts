export const STORAGE_KEYS = {
  CURRENT_MARKET: 'algotrader_current_market',
  CURRENT_TIMEFRAME: 'algotrader_current_timeframe',
} as const;

export type StorageKey = typeof STORAGE_KEYS[keyof typeof STORAGE_KEYS] | string;

export const getStoredState = <T>(key: StorageKey, defaultValue: T | null = null): T | null => {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) as T : defaultValue;
  } catch (error) {
    console.warn(`Failed to parse localStorage key "${key}":`, error);
    return defaultValue;
  }
};

export const setStoredState = (key: StorageKey, value: unknown): void => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.error(`Failed to save to localStorage key "${key}":`, error);
  }
};
