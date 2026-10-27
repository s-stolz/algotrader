import { inject, type InjectionKey } from 'vue';
import type { useBacktestCreation } from './useBacktestCreation';

type Creation = ReturnType<typeof useBacktestCreation>;
export const creationKey: InjectionKey<Creation> = Symbol('backtest creation');

export function useCreation() {
  const creation = inject(creationKey);
  if (!creation)
    throw new Error('Creation sections require their coordinator.');
  return creation;
}
