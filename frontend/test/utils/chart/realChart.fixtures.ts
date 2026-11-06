import { vi } from 'vitest';
import { createChart } from 'lightweight-charts';

// Keep the real chart model/time scale; jsdom only needs a drawing surface shim.
export function createTestChart() {
  const context = new Proxy(
    {
      measureText: (text: string) => ({ width: text.length * 7 }),
    },
    { get: (target, key) => Reflect.get(target, key) ?? (() => {}) },
  );
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    context as unknown as CanvasRenderingContext2D,
  );
  const frames = new Map<number, FrameRequestCallback>();
  let nextId = 0;
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    frames.set(++nextId, callback);
    return nextId;
  });
  vi.stubGlobal('cancelAnimationFrame', (id: number) => frames.delete(id));
  const flush = () => {
    for (let pass = 0; frames.size && pass < 5; pass++) {
      const pending = [...frames.values()];
      frames.clear();
      for (const callback of pending) callback(performance.now());
    }
  };
  vi.stubGlobal('matchMedia', () => ({
    matches: false,
    addListener() {},
    removeListener() {},
  }));
  const container = document.createElement('div');
  document.body.appendChild(container);
  const chart = createChart(container, {
    width: 800,
    height: 500,
    autoSize: false,
  });
  return {
    chart,
    flush,
    cleanup: () => {
      chart.remove();
      container.remove();
    },
  };
}
