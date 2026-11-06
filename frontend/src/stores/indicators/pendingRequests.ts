const pending = new WeakMap<object, Promise<unknown>>();

// Recovery follows the initial/configuration load, including its live subscription.
export function trackIndicatorRequests<Args extends unknown[], Result>(
  load: (id: string | null | undefined, ...args: Args) => Promise<Result>,
  getIndicator: (id: string) => object | undefined,
) {
  return (id: string | null | undefined, ...args: Args) => {
    const indicator = id ? getIndicator(id) : undefined;
    const promise = load(id, ...args);
    if (indicator) {
      pending.set(indicator, promise);
      const clear = () => {
        if (pending.get(indicator) === promise) pending.delete(indicator);
      };
      void promise.then(clear, clear);
    }
    return promise;
  };
}

export async function waitForIndicatorRequest(
  indicator: object,
): Promise<void> {
  while (pending.has(indicator)) await pending.get(indicator);
}
