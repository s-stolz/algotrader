import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  getStoredState,
  setStoredState,
  STORAGE_KEYS,
} from './localStorage';

describe('localStorage helpers', () => {
  let storage: Storage;
  let values: Record<string, string>;

  beforeEach(() => {
    values = {};
    storage = {
      get length() {
        return Object.keys(values).length;
      },
      clear: vi.fn(() => {
        values = {};
      }),
      getItem: vi.fn((key: string) => values[key] ?? null),
      key: vi.fn((index: number) => Object.keys(values)[index] ?? null),
      removeItem: vi.fn((key: string) => {
        delete values[key];
      }),
      setItem: vi.fn((key: string, value: string) => {
        values[key] = value;
      }),
    };

    vi.stubGlobal('localStorage', storage);
    Object.defineProperty(window, 'localStorage', {
      value: storage,
      configurable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('returns parsed values and falls back for missing keys', () => {
    window.localStorage.setItem(STORAGE_KEYS.CURRENT_TIMEFRAME, JSON.stringify({ value: 'M5' }));

    expect(getStoredState(STORAGE_KEYS.CURRENT_TIMEFRAME)).toEqual({ value: 'M5' });
    expect(getStoredState('missing', { fallback: true })).toEqual({ fallback: true });
  });

  it('returns defaults for malformed JSON without throwing', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    window.localStorage.setItem(STORAGE_KEYS.CURRENT_MARKET, '{bad json');

    expect(getStoredState(STORAGE_KEYS.CURRENT_MARKET, null)).toBeNull();
    expect(warn).toHaveBeenCalledWith(
      `Failed to parse localStorage key "${STORAGE_KEYS.CURRENT_MARKET}":`,
      expect.any(SyntaxError),
    );
  });

  it('does not throw when storage writes fail', () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(storage, 'setItem').mockImplementation(() => {
      throw new Error('quota exceeded');
    });

    expect(() => setStoredState(STORAGE_KEYS.CURRENT_TIMEFRAME, { value: 'H1' })).not.toThrow();
    expect(error).toHaveBeenCalledWith(
      `Failed to save to localStorage key "${STORAGE_KEYS.CURRENT_TIMEFRAME}":`,
      expect.any(Error),
    );
  });
});
