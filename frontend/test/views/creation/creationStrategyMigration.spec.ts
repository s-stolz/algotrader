import { describe, expect, it } from 'vitest';
import type {
  StrategyCatalogEntry,
  SweepDraftState,
} from '@/types/backtesterContracts';
import type { ReuseSource } from '@/views/backtestReuse';
import { initialDraft } from '@/views/creation/creationRequest';
import { applyCurrentStrategy } from '@/views/creation/creationStrategyMigration';

const selected: StrategyCatalogEntry = {
  strategy_id: 'example',
  strategy_version: 2,
  display_name: 'Example',
  parameters: [
    {
      name: 'window',
      type: 'int',
      nullable: false,
      required: false,
      default: 20,
    },
    {
      name: 'optional',
      type: 'int',
      nullable: true,
      required: false,
      default: 5,
    },
    { name: 'required', type: 'str', nullable: false, required: true },
  ],
};
function setup() {
  const draft = initialDraft();
  draft.strategy = {
    strategy_id: 'example',
    strategy_version: 1,
    parameters: { window: 30, optional: null, required: 'keep' },
  };
  const source: ReuseSource = {
    kind: 'run',
    id: 'saved',
    strategyId: 'example',
    strategyVersion: 1,
    historicalMetadata: null,
    defaultedParameters: [],
  };
  const sweep: SweepDraftState = {
    isSweep: false,
    marketIds: [],
    timeframes: [],
    allowedDirections: [],
    parameters: {},
  };
  return { draft, source, sweep };
}
describe('applyCurrentStrategy', () => {
  it('applies defaults to copied fixed values and records exact changes, including null', () => {
    const { draft, source, sweep } = setup();
    applyCurrentStrategy(selected, draft, sweep, source);
    expect(draft.strategy).toEqual({
      strategy_id: 'example',
      strategy_version: 2,
      parameters: { window: 20, optional: 5, required: 'keep' },
    });
    expect(source.appliedParameterChanges).toEqual({
      window: { saved: '30', current: '20' },
      optional: { saved: 'null', current: '5' },
    });
  });
  it('keeps explicit sweep axes while updating fixed parameters', () => {
    const { draft, source, sweep } = setup();
    sweep.isSweep = true;
    sweep.parameters.window = {
      mode: 'range',
      valuesText: '',
      stringValues: [],
      choiceIndexes: [],
      includeNull: false,
      rangeStart: 10,
      rangeStop: 50,
      rangeStep: 2,
    };
    const axes = structuredClone(sweep.parameters);
    applyCurrentStrategy(selected, draft, sweep, source);
    expect(sweep.parameters).toEqual(axes);
    expect(source.appliedParameterChanges).not.toHaveProperty('window');
    expect(draft.strategy.parameters.optional).toBe(5);
  });
  it('retains explicit values for a fresh draft rather than copied configuration', () => {
    const { draft, sweep } = setup();
    applyCurrentStrategy(selected, draft, sweep, null);
    expect(draft.strategy.parameters).toEqual({
      window: 30,
      optional: null,
      required: 'keep',
    });
  });
});
