import type { InjectionKey } from 'vue';

export const refreshBacktestActivityKey: InjectionKey<() => void> = Symbol(
  'refreshBacktestActivity',
);
