import type { ChartOptions, HandleScrollOptions } from 'lightweight-charts';

const ENABLED_HANDLE_SCROLL_OPTIONS: HandleScrollOptions = {
  mouseWheel: true,
  pressedMouseMove: true,
  horzTouchDrag: true,
  vertTouchDrag: true,
};

export function cloneHandleScrollOptions(
  handleScroll: ChartOptions['handleScroll'],
): ChartOptions['handleScroll'] {
  return typeof handleScroll === 'boolean' ? handleScroll : { ...handleScroll };
}

export function withPressedMouseMove(
  handleScroll: ChartOptions['handleScroll'],
  pressedMouseMove: boolean,
): ChartOptions['handleScroll'] {
  if (typeof handleScroll === 'boolean') {
    return handleScroll
      ? { ...ENABLED_HANDLE_SCROLL_OPTIONS, pressedMouseMove }
      : false;
  }

  return { ...handleScroll, pressedMouseMove };
}
