import { describe, expect, it } from 'vitest';
import {
  adaptHeatmapSnapshot,
  valueKey,
} from '@/types/backtest/heatmapSnapshot';
import { savedHeatmap } from '../../views/workspace/heatmap/heatmapFixtures';
describe('saved heatmap snapshot', () => {
  it('preserves complete sorted domains, explicit null and first ordinal inputs', () => {
    const { accepted, runs } = savedHeatmap();
    const snapshot = adaptHeatmapSnapshot(accepted, runs);
    expect(
      snapshot.dimensions[0].options.map((option) => option.label),
    ).toEqual(['1', '10', '—']);
    expect(snapshot.members[0].inputs['parameter:choice']).toBe(valueKey('1'));
    expect(snapshot.members[0].inputs.market).toBe(valueKey(1));
    expect(valueKey('1')).not.toBe(valueKey(1));
  });
  it.each([
    'missing',
    'duplicate',
    'ordinal',
    'id',
    'active',
    'outcomes',
    'domain',
    'type',
  ])('rejects %s mappings', (kind) => {
    const { accepted, runs } = savedHeatmap();
    if (kind === 'missing') delete runs[0].request.strategy.parameters.fast;
    if (kind === 'duplicate')
      runs[1].request = structuredClone(runs[0].request);
    if (kind === 'ordinal') runs[1].run_ordinal = 0;
    if (kind === 'id') runs[1].run_id = runs[0].run_id;
    if (kind === 'active') runs[1].status = 'running';
    if (kind === 'outcomes') accepted.outcome_counts.succeeded = 1;
    if (kind === 'domain') runs[0].request.strategy.parameters.fast = 99;
    if (kind === 'type') runs[0].request.strategy.parameters.fast = '10';
    expect(() => adaptHeatmapSnapshot(accepted, runs)).toThrow();
  });
  it('rejects partial membership before interpreting any No Run combinations', () => {
    const { accepted, runs } = savedHeatmap();
    expect(() => adaptHeatmapSnapshot(accepted, runs.slice(0, 1))).toThrow(
      'incomplete',
    );
  });
  it('maps Market IDs and whole schedules without ambiguous labels', () => {
    const { accepted, runs } = savedHeatmap();
    const saved = accepted.accepted_definition.normalized_selections;
    saved.markets.push({ symbol_id: 2, symbol: 'EURUSD', exchange: 'FX' });
    expect(() =>
      adaptHeatmapSnapshot({ ...accepted, raw_count: 24 }, runs),
    ).toThrow('ambiguous');
    runs.forEach((run) => {
      run.request.instrument = {
        symbol_id: 2,
        settlement_currency: 'USD',
        contract_multiplier: 1,
        minimum_quantity: 1,
        quantity_step: 1,
        min_move: 0.01,
      };
    });
    const schedule = {
      entry_start_minute_utc: 60,
      last_entry_minute_utc: 120,
      exit_minute_utc: 180,
    };
    saved.daily_schedules = [schedule, { ...schedule, exit_minute_utc: 240 }];
    saved.timeframes.push('H1');
    saved.allowed_directions.push('long_only');
    runs.forEach((run) => {
      run.request.execution.daily_schedule = schedule;
    });
    const snapshot = adaptHeatmapSnapshot(
      { ...accepted, raw_count: 192 },
      runs,
    );
    expect(snapshot.members[0].inputs.market).toBe('2');
    expect(
      snapshot.dimensions.find((field) => field.key === 'schedule')?.options[0]
        .label,
    ).toBe('01:00 / 02:00 / 03:00');
    expect(
      snapshot.dimensions.filter((field) => field.options.length > 1),
    ).toHaveLength(7);
  });
});
