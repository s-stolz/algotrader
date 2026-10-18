import { config } from '@vue/test-utils';

config.global.renderStubDefaultSlot = true;

const createMemoryStorage = (): Storage => {
  let values: Record<string, string> = {};

  return {
    get length() {
      return Object.keys(values).length;
    },
    clear() {
      values = {};
    },
    getItem(key: string) {
      return values[key] ?? null;
    },
    key(index: number) {
      return Object.keys(values)[index] ?? null;
    },
    removeItem(key: string) {
      delete values[key];
    },
    setItem(key: string, value: string) {
      values[key] = value;
    },
  };
};

if (typeof globalThis.localStorage?.getItem !== 'function') {
  const storage = createMemoryStorage();

  Object.defineProperty(globalThis, 'localStorage', {
    value: storage,
    configurable: true,
  });

  if (typeof window !== 'undefined') {
    Object.defineProperty(window, 'localStorage', {
      value: storage,
      configurable: true,
    });
  }
}
