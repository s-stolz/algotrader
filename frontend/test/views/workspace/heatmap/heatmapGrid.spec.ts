import { describe, expect, it } from 'vitest';
import {
  adaptHeatmapSnapshot,
  valueKey,
} from '@/types/backtest/heatmapSnapshot';
import { heatmapGrid } from '@/views/workspace/heatmap/heatmapGrid';
import { savedHeatmap } from './heatmapFixtures';
describe('full heatmap grid', () => {
  it('keeps sparse domains, empty slices, and Run identity across swaps', () => {
    const { accepted, runs } = savedHeatmap();
    const snapshot = adaptHeatmapSnapshot(accepted, runs);
    const fixed = { ...snapshot.members[0].inputs };
    const cells = heatmapGrid(
      snapshot,
      'parameter:fast',
      'parameter:slow',
      fixed,
      'return',
    );
    expect(cells).toHaveLength(6);
    expect(cells.filter((cell) => cell.state === 'excluded')).toHaveLength(4);
    const swapped = heatmapGrid(
      snapshot,
      'parameter:slow',
      'parameter:fast',
      fixed,
      'return',
    );
    for (const cell of cells)
      expect(
        swapped.find((other) => other.x === cell.y && other.y === cell.x)?.run
          ?.run_id,
      ).toBe(cell.run?.run_id);
    fixed['parameter:choice'] = valueKey('two');
    expect(
      heatmapGrid(
        snapshot,
        'parameter:fast',
        'parameter:slow',
        fixed,
        'factor',
      ).filter((cell) => cell.run),
    ).toHaveLength(1);
    fixed['parameter:choice'] = valueKey('absent');
    expect(
      heatmapGrid(
        snapshot,
        'parameter:fast',
        'parameter:slow',
        fixed,
        'return',
      ).every((cell) => cell.state === 'excluded'),
    ).toBe(true);
    expect(
      heatmapGrid(
        snapshot,
        'parameter:fast',
        'parameter:fast',
        fixed,
        'return',
      ),
    ).toEqual([]);
  });
  it('keeps successful unavailable Runs actionable and exposes exact hover values', () => {
    const { accepted, runs } = savedHeatmap();
    const snapshot = adaptHeatmapSnapshot(accepted, runs);
    const cells = heatmapGrid(
      snapshot,
      'parameter:fast',
      'parameter:slow',
      snapshot.members[0].inputs,
      'return',
    );
    expect(cells.find((cell) => cell.run === runs[0])?.description).toContain(
      '-10.12345%',
    );
    const unavailable = heatmapGrid(
      snapshot,
      'parameter:fast',
      'parameter:slow',
      snapshot.members[2].inputs,
      'factor',
    ).find((cell) => cell.run === runs[2]);
    expect(unavailable?.state).toBe('unavailable');
    expect(unavailable?.run?.status).toBe('succeeded');
  });
});
