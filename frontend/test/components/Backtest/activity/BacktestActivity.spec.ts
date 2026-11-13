import { defineComponent } from 'vue';
import { createPinia, setActivePinia } from 'pinia';
import { flushPromises, mount } from '@vue/test-utils';
import {
  beforeEach,
  afterEach,
  describe,
  expect,
  it,
  onTestFinished,
  vi,
} from 'vitest';
import { fetchBacktestQueue, getBacktest } from '@/api/backtesterClient';
import BacktestActivity from '@/components/Backtest/activity/BacktestActivity.vue';
import {
  emitBacktestChange,
  emitBacktestEvent,
  installBacktestSocket,
} from '../../../backtestEventSocket';
import { backtest, healthySnapshot, NOW } from './backtestActivityFixtures';

vi.mock('@/api/backtesterClient', () => ({
  fetchBacktestQueue: vi.fn(),
  getBacktest: vi.fn(),
}));
const Popover = defineComponent({
  props: ['show', 'disabled'],
  emits: ['update:show'],
  template: `
    <div>
      <div @click="!disabled && $emit('update:show', !show)">
        <slot name="trigger" />
      </div>
      <div v-if="show && !disabled"><slot /></div>
    </div>`,
});
function mountActivity() {
  const wrapper = mount(BacktestActivity, {
    attachTo: document.body,
    global: { stubs: { BasePopover: Popover } },
  });
  onTestFinished(() => wrapper.unmount());
  return wrapper;
}
async function openActivity() {
  const wrapper = mountActivity();
  await flushPromises();
  await wrapper.get('[data-testid="activity-toggle"]').trigger('click');
  return wrapper;
}

describe('Backtest activity', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    installBacktestSocket();
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    vi.mocked(fetchBacktestQueue)
      .mockReset()
      .mockResolvedValue(healthySnapshot);
    vi.mocked(getBacktest)
      .mockReset()
      .mockImplementation(async (id) => ({
        ...backtest,
        backtest_id: id,
        name: id === 'backtest-1' ? 'SMA crossover' : 'Next experiment',
        settled_count: 1,
        total_count: 2,
      }));
  });
  afterEach(() => vi.useRealTimers());

  it('shows running and queued work with experiment progress and inspection links', async () => {
    const wrapper = await openActivity();
    expect(wrapper.get('[data-testid="activity-toggle"]').text()).toBe(
      '1 running · 1 queued',
    );
    const active = wrapper.get('[data-testid="activity-backtest-backtest-1"]');
    expect(active.text()).toContain('SMA crossover');
    expect(active.text()).toContain('Run #1 · Running');
    expect(active.get('progress').attributes()).toMatchObject({
      value: '1',
      max: '2',
    });
    const queued = wrapper.get('[data-testid="activity-backtest-waiting"]');
    expect(queued.text()).toContain('Run #1 · Queued');
    expect(queued.get('progress').attributes()).toMatchObject({
      value: '0',
      max: '1',
    });
    await queued.trigger('click');
    expect(wrapper.emitted('inspect')).toEqual([['waiting']]);
    expect(
      wrapper
        .get('[data-testid="activity-toggle"]')
        .attributes('aria-expanded'),
    ).toBe('false');
  });

  it('offers a quiet online badge when the worker is idle', async () => {
    vi.mocked(fetchBacktestQueue).mockResolvedValue({
      ...healthySnapshot,
      active_run: null,
      queued: [],
    });
    const wrapper = mountActivity();
    await flushPromises();
    const trigger = wrapper.get('[data-testid="activity-toggle"]');
    expect(trigger.text()).toBe('Worker online');
    expect(trigger.attributes('disabled')).toBeDefined();
  });

  it.each([
    ['stale', 'Worker not responding'],
    ['unavailable', 'Worker offline'],
    ['faulted', 'Worker error'],
  ] as const)(
    'identifies %s health while retaining last known activity',
    async (availability, label) => {
      vi.mocked(fetchBacktestQueue).mockResolvedValue({
        ...healthySnapshot,
        availability,
      });
      const wrapper = await openActivity();
      expect(wrapper.get('[data-testid="activity-toggle"]').text()).toBe(label);
      expect(
        wrapper.get('[data-testid="activity-backtest-backtest-1"]').text(),
      ).toContain('Was running');
    },
  );

  it('retries a failed status request', async () => {
    vi.mocked(fetchBacktestQueue).mockRejectedValueOnce(
      new Error('Read failed'),
    );
    const wrapper = await openActivity();
    expect(wrapper.get('[data-testid="activity-toggle"]').text()).toBe(
      'Status unavailable',
    );
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Check again')!
      .trigger('click');
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
    expect(wrapper.get('[data-testid="activity-toggle"]').text()).toBe(
      '1 running · 1 queued',
    );
  });

  it('keeps queued progress available when experiment details fail', async () => {
    vi.mocked(getBacktest).mockRejectedValue(new Error('Details unavailable'));
    const wrapper = await openActivity();
    expect(
      wrapper
        .get('[data-testid="activity-backtest-waiting"] progress')
        .attributes('max'),
    ).toBe('1');
  });

  it('updates on events and returns focus when dismissed with Escape', async () => {
    const wrapper = await openActivity();
    emitBacktestChange();
    await flushPromises();
    expect(fetchBacktestQueue).toHaveBeenCalledTimes(2);
    emitBacktestEvent({ type: 'backtestConnection', connected: false });
    await flushPromises();
    expect(wrapper.get('[data-testid="activity-toggle"]').text()).toBe(
      'Connection lost',
    );
    await wrapper
      .get('[aria-label="Worker status details"]')
      .trigger('keydown', { key: 'Escape' });
    const trigger = wrapper.get('[data-testid="activity-toggle"]');
    expect(document.activeElement).toBe(trigger.element);
    expect(trigger.attributes('aria-expanded')).toBe('false');
  });
});
