<template>
  <div class="replay-charts" aria-label="Exact equity and drawdown charts">
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
import type { EquityReplayPoint } from '@/types/backtesterContracts';

const props = defineProps<{ points: EquityReplayPoint[] }>();
const equityContainer = ref<HTMLElement | null>(null);
const drawdownContainer = ref<HTMLElement | null>(null);
let equityChart: IChartApi | null = null;
let drawdownChart: IChartApi | null = null;
let resizeObserver: ResizeObserver | null = null;

function render(): void {
  if (!equityChart || !drawdownChart) return;
  const equity = equityChart.addSeries(LineSeries, { color: '#33c6bd', lineWidth: 2 });
  const drawdown = drawdownChart.addSeries(LineSeries, { color: '#e38282', lineWidth: 2 });
  equity.setData(props.points.map((point) => ({
    time: Math.floor(point.timestamp_ms / 1000) as UTCTimestamp, value: point.equity,
  })));
  drawdown.setData(props.points.map((point) => ({
    time: Math.floor(point.timestamp_ms / 1000) as UTCTimestamp, value: point.drawdown_pct,
  })));
  equityChart.timeScale().fitContent();
  drawdownChart.timeScale().fitContent();
}

onMounted(() => {
  if (!equityContainer.value || !drawdownContainer.value) return;
  const options = { layout: { background: { color: '#121923' }, textColor: '#c9d3dc' },
    width: equityContainer.value.clientWidth, height: 250 };
  equityChart = createChart(equityContainer.value, options);
  drawdownChart = createChart(drawdownContainer.value, { ...options,
    width: drawdownContainer.value.clientWidth });
  render();
  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => {
      equityChart?.applyOptions({ width: equityContainer.value?.clientWidth ?? 0 });
      drawdownChart?.applyOptions({ width: drawdownContainer.value?.clientWidth ?? 0 });
    });
    resizeObserver.observe(equityContainer.value);
    resizeObserver.observe(drawdownContainer.value);
  }
});
watch(() => props.points, () => {
  equityChart?.remove();
  drawdownChart?.remove();
  equityChart = null;
  drawdownChart = null;
  if (equityContainer.value && drawdownContainer.value) {
    equityChart = createChart(equityContainer.value, { width: equityContainer.value.clientWidth, height: 250 });
    drawdownChart = createChart(drawdownContainer.value, { width: drawdownContainer.value.clientWidth, height: 250 });
    render();
  }
});
onUnmounted(() => {
  resizeObserver?.disconnect();
  equityChart?.remove();
  drawdownChart?.remove();
});
</script>

<style scoped>
.replay-charts { width: 100%; display: grid; gap: 20px; margin-top: 24px; }
.replay-charts section { min-width: 0; width: 100%; }
.replay-charts h3 { font-size: 15px; margin: 0 0 8px; }
.chart { width: 100%; min-height: 250px; }
</style>
