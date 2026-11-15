import { flushPromises } from '@vue/test-utils';
import { NSelect } from 'naive-ui';
import { describe, expect, it, vi } from 'vitest';
import { fetchStrategyCatalog, previewBacktest } from '@/api/backtesterClient';
import {
  catalog,
  creationSetup,
  openDrawer,
  advancePreview,
} from './creationFixtures';

vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktest: vi.fn(),
  previewBacktest: vi.fn(),
  fetchBacktestCapabilities: vi.fn(),
}));

describe('risk sizing stop-loss validation', () => {
  creationSetup();
  it.each(['risk', 'equity_risk'])(
    'highlights a missing strategy stop for %s',
    async (mode) => {
      vi.mocked(fetchStrategyCatalog).mockResolvedValue(
        catalog.map((strategy) => ({
          ...strategy,
          parameters: strategy.parameters.map((parameter) => ({
            ...parameter,
            ...(parameter.name === 'stop_loss_pct'
              ? { purpose: 'stop_loss' as const }
              : {}),
          })),
        })),
      );
      const wrapper = openDrawer();
      await advancePreview();
      const select = (label: string) =>
        wrapper
          .findAllComponents(NSelect)
          .find((item) => item.attributes('aria-label') === label)!;
      const previews = vi.mocked(previewBacktest).mock.calls.length;
      select('Sizing mode').vm.$emit('update:value', mode);
      await advancePreview();
      expect(select('Stop-loss source').props('status')).toBe('error');
      const stopField = document.querySelector(
        '[data-setup-field="stop_loss"]',
      )!;
      expect(stopField.querySelector('[role="alert"]')).toBeNull();
      expect(stopField.querySelector('p')).toBeNull();
      const errorIcon = stopField.querySelector(
        '[aria-label="Error: stop-loss"]',
      )!;
      expect(errorIcon).not.toBeNull();
      errorIcon.dispatchEvent(new FocusEvent('focus'));
      await flushPromises();
      expect(document.body.textContent).toContain(
        'Risk sizing requires an initial stop',
      );
      errorIcon.dispatchEvent(new FocusEvent('blur'));
      expect(previewBacktest).toHaveBeenCalledTimes(previews);
      select('Stop-loss source').vm.$emit('update:value', 'distance');
      await advancePreview();
      expect(select('Stop-loss source').props('status')).toBeUndefined();
      expect(previewBacktest).toHaveBeenCalledTimes(previews + 1);
      select('Stop-loss source').vm.$emit('update:value', 'none');
      await flushPromises();
      expect(select('Stop-loss source').props('status')).toBe('error');
      select('Sizing mode').vm.$emit('update:value', 'units');
      await flushPromises();
      expect(select('Stop-loss source').props('status')).toBeUndefined();
    },
  );
});
