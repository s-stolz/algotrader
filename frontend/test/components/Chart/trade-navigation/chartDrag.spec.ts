import { afterEach, expect, it, vi } from 'vitest';
import { createChartDrag } from '@/components/Chart/trade-navigation/chartDrag';

const element = document.createElement('div');
afterEach(() => element.remove());
it.each(['mouseup', 'blur', 'cancel'])(
  'releases waiting chart batches on %s',
  async (end) => {
    document.body.append(element);
    const drag = createChartDrag(() => element);
    drag.begin();
    try {
      window.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      expect(drag.active).toBe(false);
      element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      const resumed = vi.fn();
      const waiting = drag.wait().then(resumed);
      await Promise.resolve();
      expect(resumed).not.toHaveBeenCalled();
      if (end === 'cancel') drag.stop();
      else window.dispatchEvent(new Event(end));
      await waiting;
      expect(resumed).toHaveBeenCalledOnce();
      expect(drag.active).toBe(false);
    } finally {
      drag.stop();
    }
  },
);
