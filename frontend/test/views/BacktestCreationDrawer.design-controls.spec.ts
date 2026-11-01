import { readFileSync } from 'node:fs';
import { compileStyle } from '@vue/compiler-sfc';
import { flushPromises } from '@vue/test-utils';
import { NInputNumber, NSelect } from 'naive-ui';
import { describe, expect, it, onTestFinished, vi } from 'vitest';
import { submitBacktestRun } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { openDrawer, standaloneSetup } from './creationFixtures';

vi.mock('@/api/backtesterClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/backtesterClient')>()),
  fetchStrategyCatalog: vi.fn(),
  submitBacktestRun: vi.fn(),
  submitBacktestBatch: vi.fn(),
  previewParameterSweep: vi.fn(),
  fetchSweepCapabilities: vi.fn(),
}));

describe('creation design controls', () => {
  standaloneSetup();

  it('lays out the teleported footer with the count left and actions right', async () => {
    const wrapper = openDrawer();
    const style = document.createElement('style');
    onTestFinished(() => {
      wrapper.unmount();
      style.remove();
    });
    await flushPromises();
    const footer = document.querySelector<HTMLElement>('.creation-footer')!;
    const scopeId = footer
      .getAttributeNames()
      .find((name) => name.startsWith('data-v-'))!;
    expect(scopeId).toBeTruthy();
    style.textContent = compileStyle({
      source: readFileSync('src/views/creation/creation.css', 'utf8'),
      filename: 'creation.css',
      id: scopeId,
      scoped: true,
    }).code;
    document.head.append(style);
    const actions = footer.querySelector<HTMLElement>('.creation-actions')!;
    expect(getComputedStyle(footer).display).toBe('flex');
    expect(getComputedStyle(footer).justifyContent).toBe('space-between');
    expect(getComputedStyle(actions).display).toBe('flex');
    const fields = document.querySelector<HTMLElement>('.creation-fields')!;
    const strategyLabel =
      document.querySelector<HTMLElement>('.strategy-label')!;
    const label = strategyLabel.parentElement!;
    expect(getComputedStyle(fields).display).toBe('grid');
    expect(getComputedStyle(label).display).toBe('grid');
    expect(getComputedStyle(label).gap).toBe('var(--design-space-xs)');
    expect(getComputedStyle(strategyLabel).alignItems).toBe('center');
  });

  it('keeps the strategy menu open without activating its version hint', async () => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    onTestFinished(() => {
      vi.unstubAllGlobals();
    });
    useBacktestWorkspaceStore().reuseSource = {
      kind: 'run',
      id: 'saved',
      strategyId: 'sma_crossover',
      strategyVersion: 2,
      historicalMetadata: null,
      defaultedParameters: [],
    };
    const wrapper = openDrawer();
    await flushPromises();
    const hint = document.querySelector<HTMLElement>(
      '[data-testid="reuse-version-review"]',
    )!;
    const hintClick = vi.fn();
    hint.addEventListener('click', hintClick);
    const select = wrapper
      .findAllComponents(NSelect)
      .find(
        (control) => control.attributes('data-testid') === 'creation-strategy',
      )!;
    const trigger = select.get('.n-base-selection').element as HTMLElement;
    trigger.click();
    await new Promise((resolve) => requestAnimationFrame(resolve));
    await flushPromises();
    expect(hintClick).not.toHaveBeenCalled();
    expect(trigger.classList.contains('n-base-selection--active')).toBe(true);
    expect(document.querySelector('.n-select-menu')).not.toBeNull();
    wrapper.unmount();
  });

  it('retains numeric keyboard editing and requires explicit submission', async () => {
    vi.mocked(submitBacktestRun).mockResolvedValue('keyboard-run');
    const wrapper = openDrawer();
    await flushPromises();
    const capital = wrapper
      .findAllComponents(NInputNumber)
      .find(
        (control) => control.attributes('data-testid') === 'creation-capital',
      )!;
    const input = capital.get('input');
    await input.setValue('12345');
    await input.trigger('keydown', { key: 'Enter' });
    await input.trigger('blur');
    await flushPromises();
    expect(useBacktestWorkspaceStore().creationDraft?.initial_capital).toBe(
      12345,
    );
    expect(submitBacktestRun).not.toHaveBeenCalled();
    document
      .querySelector<HTMLButtonElement>('[data-testid="creation-submit"]')!
      .click();
    await flushPromises();
    expect(submitBacktestRun).toHaveBeenCalledWith(
      expect.objectContaining({ initial_capital: 12345 }),
    );
    wrapper.unmount();
  });
});
