import { describe, expect, it } from 'vitest';
import { effectScope, shallowRef } from 'vue';
import { useParameterHeatmap } from '@/views/workspace/heatmap/useParameterHeatmap';
import { savedHeatmap } from './heatmapFixtures';
describe('heatmap controls', () => {
  it('initializes fixed inputs and retains controls through refresh and swaps', () => {
    const { accepted, runs } = savedHeatmap();
    const saved = shallowRef({ backtest: accepted, runs });
    const scope = effectScope();
    const model = scope.run(() => useParameterHeatmap(saved))!;
    expect([model.x.value, model.y.value, model.metric.value]).toEqual([
      null,
      null,
      null,
    ]);
    expect(model.ready.value).toBe(false);
    model.x.value = 'parameter:fast';
    model.y.value = 'parameter:slow';
    model.metric.value = 'return';
    expect(model.cells.value).toHaveLength(6);
    expect(model.fixedDimensions.value.map((field) => field.key)).toEqual([
      'parameter:choice',
    ]);
    model.fixed.value['parameter:choice'] = '"two"';
    const previous = model.cells.value.find((cell) => cell.run)?.run?.run_id;
    model.swap();
    expect(model.cells.value.find((cell) => cell.run)?.run?.run_id).toBe(
      previous,
    );
    saved.value = { backtest: { ...accepted }, runs: [...runs] };
    expect(model.fixed.value['parameter:choice']).toBe('"two"');
    expect(model.metric.value).toBe('return');
    expect(model.bounds.value).toEqual([-10.12345, 1000]);
    saved.value = {
      backtest: { ...accepted, backtest_id: 'B' },
      runs: runs.map((run) => ({ ...run, backtest_id: 'B' })),
    };
    expect([model.x.value, model.y.value, model.metric.value]).toEqual([
      null,
      null,
      null,
    ]);
    expect(model.fixed.value['parameter:choice']).toBe('"1"');
    scope.stop();
  });
  it('has no valid grid with fewer than two varying numeric axes', () => {
    const { accepted, runs } = savedHeatmap();
    accepted.accepted_definition.normalized_selections.parameters.slow.values =
      [20];
    accepted.raw_count = 6;
    runs.forEach((run) => {
      run.request.strategy.parameters.slow = 20;
    });
    const scope = effectScope();
    const model = scope.run(() =>
      useParameterHeatmap(shallowRef({ backtest: accepted, runs })),
    )!;
    expect(model.adapted.value.error).toBeNull();
    expect(model.axes.value).toHaveLength(1);
    model.x.value = 'parameter:fast';
    model.y.value = 'parameter:slow';
    model.metric.value = 'return';
    expect(model.ready.value).toBe(false);
    expect(model.cells.value).toEqual([]);
    scope.stop();
  });
});
