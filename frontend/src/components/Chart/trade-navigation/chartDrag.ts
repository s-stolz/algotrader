// A drag caches the chart's base index. Installing newer bars before release
// invalidates that cached origin, so streamed batches wait for the gesture.
export function createChartDrag(getContainer: () => HTMLElement | null) {
  let dragging = false;
  const waiters = new Set<() => void>();
  function release() {
    dragging = false;
    for (const resolve of waiters) resolve();
    waiters.clear();
  }
  function start(event: MouseEvent) {
    if (
      event.button === 0 &&
      event.target instanceof Node &&
      getContainer()?.contains(event.target)
    )
      dragging = true;
  }
  function stop() {
    window.removeEventListener('mousedown', start, true);
    window.removeEventListener('mouseup', release);
    window.removeEventListener('blur', release);
    release();
  }
  return {
    get active() {
      return dragging;
    },
    begin() {
      stop();
      window.addEventListener('mousedown', start, true);
      window.addEventListener('mouseup', release);
      window.addEventListener('blur', release);
    },
    wait: () =>
      new Promise<void>((resolve) => {
        if (dragging) waiters.add(resolve);
        else resolve();
      }),
    stop,
  };
}
