<template>
  <div class="replay-charts" aria-label="Exact equity and drawdown charts">
    <header class="chart-header">
      <ul class="series-legend" aria-label="Compared runs">
        <li v-for="run in series" :key="run.runId" :title="run.name">
          <span class="series-swatch" :style="{ background: seriesColor(run) }" />
          {{ run.ordinal == null ? run.runId.slice(0, 8) : `#${run.ordinal + 1}` }}
        </li>
      </ul>
      <span v-if="sampled" class="sampling-note" title="Sampled exact replay points, preserving the first and last points and the maximum drawdown peak and trough.">Sampled curve</span>
    </header>
    <section aria-label="Equity chart">
      <h3>Equity <span>Account value</span></h3>
      <div ref="equityContainer" class="chart" data-testid="equity-chart" />
    </section>
    <section aria-label="Drawdown chart">
      <h3>Drawdown <span>Below peak · %</span></h3>
      <div ref="drawdownContainer" class="chart" data-testid="drawdown-chart" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { createChart, LineSeries, type AutoscaleInfo, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts';
import type { ReplaySeries } from './backtestComparison';

const props = defineProps<{ series: ReplaySeries[]; sampled?: boolean }>();
const equityContainer = ref<HTMLElement | null>(null);
const drawdownContainer = ref<HTMLElement | null>(null);
let equityChart: IChartApi | null = null;
let drawdownChart: IChartApi | null = null;
let resizeObserver: ResizeObserver | null = null;

function seriesColor(run: ReplaySeries): string {
  let hash = 0;
  for (const character of run.runId) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  const hue = run.ordinal == null ? hash % 360 : (run.ordinal * 137.508) % 360;
  return `hsl(${hue} 72% 62%)`;
}

const rendered = new Map<string, {
  equity: ISeriesApi<'Line'>; drawdown: ISeriesApi<'Line'>; points: ReplaySeries['points'];
}>();

function fitCharts(): void {
  // Compared runs can contribute different timestamps; allow subpixel spacing
  // even when their combined history is wider than the chart's default limit.
  const pointCount = props.series.reduce((count, run) => count + run.points.length, 0);
  for (const chart of [equityChart, drawdownChart]) {
    chart?.applyOptions({ timeScale: { minBarSpacing: 1 / (pointCount + 1) } });
    chart?.timeScale().fitContent();
  }
}

function render(): void {
  if (!equityChart || !drawdownChart) return;
  let maxDrawdown = 0;
  for (const run of props.series) {
    for (const point of run.points) maxDrawdown = Math.max(maxDrawdown, Math.abs(point.drawdown_pct));
  }
  const drawdownPrecision = maxDrawdown > 0
    ? Math.min(8, Math.max(2, 2 - Math.floor(Math.log10(maxDrawdown)))) : 2;
  const ids = new Set(props.series.map((run) => run.runId));
  for (const [id, series] of rendered) {
    if (ids.has(id)) continue;
    equityChart.removeSeries(series.equity);
    drawdownChart.removeSeries(series.drawdown);
    rendered.delete(id);
  }
  for (const run of props.series) {
    let series = rendered.get(run.runId);
    if (!series) {
      const options = { color: seriesColor(run), lineWidth: 2 as const, title: '',
        priceLineVisible: false, lastValueVisible: false };
      series = { equity: equityChart.addSeries(LineSeries, options),
        drawdown: drawdownChart.addSeries(LineSeries, { ...options,
          autoscaleInfoProvider: (original: () => AutoscaleInfo | null) => {
            const info = original();
            return info?.priceRange ? { ...info, priceRange: {
              minValue: Math.min(info.priceRange.minValue, 0), maxValue: 0,
            } } : null;
          },
        }), points: [] };
      rendered.set(run.runId, series);
    }
    const minMove = 10 ** -drawdownPrecision;
    series.drawdown.applyOptions({ priceFormat: { type: 'custom', minMove,
      formatter: (value: number) => `${(Math.abs(value) < minMove / 2 ? 0 : value).toFixed(drawdownPrecision)}%`,
    } });
    if (series.points === run.points) continue;
    series.equity.setData(run.points.map((point) => ({
      time: Math.floor(point.timestamp_ms / 1000) as UTCTimestamp, value: point.equity,
    })));
    series.drawdown.setData(run.points.map((point) => ({
      time: Math.floor(point.timestamp_ms / 1000) as UTCTimestamp, value: point.drawdown_pct,
    })));
    series.points = run.points;
  }
  fitCharts();
}

function createCharts(): void {
  if (!equityContainer.value || !drawdownContainer.value) return;
  const options = { layout: { background: { color: '#161e28' }, textColor: '#93a5b5',
    fontFamily: 'Inter, -apple-system, sans-serif', fontSize: 11 },
    grid: { vertLines: { visible: false }, horzLines: { color: '#26313d' } },
    rightPriceScale: { visible: true, autoScale: true, minimumWidth: 104,
      borderVisible: false, scaleMargins: { top: 0.1, bottom: 0.1 } },
    timeScale: { borderColor: '#34414e', timeVisible: true, secondsVisible: false,
      rightOffset: 0, fixLeftEdge: true, fixRightEdge: true, lockVisibleTimeRangeOnResize: true },
    handleScroll: false, handleScale: false,
    width: equityContainer.value.clientWidth, height: 280 };
  equityChart = createChart(equityContainer.value, options);
  drawdownChart = createChart(drawdownContainer.value, { ...options,
    width: drawdownContainer.value.clientWidth, height: 220 });
  render();
}
onMounted(() => {
  createCharts();
  if (typeof ResizeObserver !== 'undefined' && equityContainer.value && drawdownContainer.value) {
    resizeObserver = new ResizeObserver(() => {
      equityChart?.applyOptions({ width: equityContainer.value?.clientWidth ?? 0 });
      drawdownChart?.applyOptions({ width: drawdownContainer.value?.clientWidth ?? 0 });
      fitCharts();
    });
    resizeObserver.observe(equityContainer.value);
    resizeObserver.observe(drawdownContainer.value);
  }
});
watch(() => props.series, render);
onUnmounted(() => {
  resizeObserver?.disconnect();
  equityChart?.remove();
  drawdownChart?.remove();
});
</script>

<style scoped>
.replay-charts { min-width: 0; width: 100%; display: grid; gap: 0; margin-top: 16px; border: 1px solid #303c49; border-radius: 10px; overflow: hidden; background: #161e28; }
.chart-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; padding: 14px 18px; border-bottom: 1px solid #26313d; }
.series-legend { display: flex; flex-wrap: wrap; gap: 10px 20px; margin: 0; padding: 0; list-style: none; font-size: 12px; color: #cbd5df; }
.series-legend li { display: flex; align-items: center; gap: 7px; }
.series-swatch { width: 16px; height: 3px; border-radius: 2px; }
.sampling-note { font-size: 11px; color: #93a5b5; }
.replay-charts section { min-width: 0; width: 100%; padding: 16px 12px 8px; box-sizing: border-box; }
.replay-charts section + section { border-top: 1px solid #26313d; }
.replay-charts h3 { display: flex; align-items: baseline; gap: 10px; font-size: 14px; margin: 0 6px 12px; color: #dce5ed; }
.replay-charts h3 span { font-size: 11px; font-weight: 400; color: #93a5b5; }
.chart { width: 100%; min-width: 0; }
</style>
