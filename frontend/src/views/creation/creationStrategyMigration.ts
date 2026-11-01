import type {
  StrategyCatalogEntry,
  SweepDraftState,
} from '@/types/backtesterContracts';
import type { ReuseSource } from '../backtestReuse';
import type { DraftRequest } from './creationRequest';
import { defaults } from './creationParameters';

export function applyCurrentStrategy(
  selected: StrategyCatalogEntry,
  draft: DraftRequest,
  sweep: SweepDraftState,
  source: ReuseSource | null,
): void {
  const parameters = defaults(selected);
  const copying = source?.strategyId === selected.strategy_id;
  const changes: NonNullable<ReuseSource['appliedParameterChanges']> = {};
  for (const parameter of selected.parameters) {
    const name = parameter.name;
    const saved = draft.strategy.parameters[name];
    const axis = sweep.parameters[name];
    const explicitSweep = sweep.isSweep && axis && axis.mode !== 'constant';
    if (!copying || explicitSweep || !Object.hasOwn(parameter, 'default')) {
      if (Object.hasOwn(draft.strategy.parameters, name))
        parameters[name] = saved;
      continue;
    }
    const previous = Object.hasOwn(draft.strategy.parameters, name)
      ? saved
      : source.defaultedParameters.includes(name)
        ? source.historicalMetadata?.parameters.find(
            (item) => item.name === name,
          )?.default
        : saved;
    if (JSON.stringify(previous) !== JSON.stringify(parameters[name])) {
      changes[name] = {
        saved: previous === undefined ? 'Not set' : JSON.stringify(previous),
        current: JSON.stringify(parameters[name]),
      };
    }
  }
  if (copying) source.appliedParameterChanges = changes;
  draft.strategy = {
    strategy_id: selected.strategy_id,
    strategy_version: selected.strategy_version,
    parameters,
  };
}
