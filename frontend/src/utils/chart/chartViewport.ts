import type { IChartApi } from 'lightweight-charts';

export function captureChartViewport(
  chart: IChartApi | null | undefined,
): () => void {
  if (!chart) return () => {};
  const scale = chart.timeScale();
  const range = scale.getVisibleLogicalRange();
  const anchor = scale.getVisibleRange()?.to;
  const before = anchor === undefined ? null : scale.timeToIndex(anchor);
  return () => {
    if (!range) return;
    const after = anchor === undefined ? null : scale.timeToIndex(anchor);
    const shift = before === null || after === null ? 0 : after - before;
    // Translate around an existing candle while retaining bar spacing and whitespace.
    scale.setVisibleLogicalRange({
      from: range.from + shift,
      to: range.to + shift,
    });
  };
}
