// Storage key constants
export const STORAGE_KEYS = {
  CURRENT_MARKET: 'algotrader_current_market',
  CURRENT_TIMEFRAME: 'algotrader_current_timeframe',
};

// Safe getter with JSON parsing and error handling
export const getStoredState = (key, defaultValue = null) => {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  } catch (error) {
    console.warn(`Failed to parse localStorage key "${key}":`, error);
    return defaultValue;
  }
};

// Safe setter with JSON stringification and error handling
export const setStoredState = (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.error(`Failed to save to localStorage key "${key}":`, error);
  }
};
