import { inject, type InjectionKey } from 'vue';

export const designScopeKey: InjectionKey<boolean> = Symbol('design-scope');

// A missing scope deliberately retains the existing Base-control appearance.
export function useDesignScope(): boolean {
  return inject(designScopeKey, false);
}
