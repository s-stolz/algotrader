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

// jsdom has no scrolling implementation; keep the DOM position observable to modal tests.
if (!Element.prototype.scrollTo) {
  Element.prototype.scrollTo = function (options: ScrollToOptions | number = {}, y?: number): void {
    this.scrollTop = typeof options === 'number' ? y ?? 0 : options.top ?? this.scrollTop;
    this.scrollLeft = typeof options === 'number' ? options : options.left ?? this.scrollLeft;
  };
}
