<template>
  <div class="replay-charts" aria-label="Exact equity and drawdown charts">
    <ul class="series-legend" aria-label="Compared runs">
      <li v-for="run in series" :key="run.runId" :style="{ color: seriesColor(run) }">
        {{ run.name }} · {{ run.runId }}
      </li>
    </ul>
    <section aria-label="Equity chart">
      <h3>Equity</h3>
      <div ref="equityContainer" class="chart" data-testid="equity-chart" />
    </section>
    <section aria-label="Drawdown chart">
      <h3>Drawdown (%)</h3>
      <div ref="drawdownContainer" class="chart" data-testid="drawdown-chart" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { createChart, LineSeries, type IChartApi, type UTCTimestamp } from 'lightweight-charts';
import type { ReplaySeries } from './backtestComparison';

const props = defineProps<{ series: ReplaySeries[] }>();
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

function render(): void {
  if (!equityChart || !drawdownChart) return;
  for (const run of props.series) {
    const color = seriesColor(run);
    const equity = equityChart.addSeries(LineSeries, { color, lineWidth: 2,
      title: run.name });
    const drawdown = drawdownChart.addSeries(LineSeries, { color, lineWidth: 2,
      title: run.name });
    equity.setData(run.points.map((point) => ({
      time: Math.floor(point.timestamp_ms / 1000) as UTCTimestamp, value: point.equity,
    })));
    drawdown.setData(run.points.map((point) => ({
      time: Math.floor(point.timestamp_ms / 1000) as UTCTimestamp, value: point.drawdown_pct,
    })));
  }
  equityChart.timeScale().fitContent();
  drawdownChart.timeScale().fitContent();
}

function createCharts(): void {
  if (!equityContainer.value || !drawdownContainer.value) return;
  const options = { layout: { background: { color: '#121923' }, textColor: '#c9d3dc' },
    width: equityContainer.value.clientWidth, height: 250 };
  equityChart = createChart(equityContainer.value, options);
  drawdownChart = createChart(drawdownContainer.value, { ...options,
    width: drawdownContainer.value.clientWidth });
  render();
}
onMounted(() => {
  createCharts();
  if (typeof ResizeObserver !== 'undefined' && equityContainer.value && drawdownContainer.value) {
    resizeObserver = new ResizeObserver(() => {
      equityChart?.applyOptions({ width: equityContainer.value?.clientWidth ?? 0 });
      drawdownChart?.applyOptions({ width: drawdownContainer.value?.clientWidth ?? 0 });
    });
    resizeObserver.observe(equityContainer.value);
    resizeObserver.observe(drawdownContainer.value);
  }
});
watch(() => props.series, () => {
  equityChart?.remove();
  drawdownChart?.remove();
  equityChart = null;
  drawdownChart = null;
  createCharts();
});
onUnmounted(() => {
  resizeObserver?.disconnect();
  equityChart?.remove();
  drawdownChart?.remove();
});
</script>

<style scoped>
.replay-charts { width: 100%; display: grid; gap: 20px; margin-top: 24px; }
.series-legend { display: flex; flex-wrap: wrap; gap: 8px 20px; margin: 0; padding-left: 20px; }
.replay-charts section { min-width: 0; width: 100%; }
.replay-charts h3 { font-size: 15px; margin: 0 0 8px; }
.chart { width: 100%; min-height: 250px; }
</style>
