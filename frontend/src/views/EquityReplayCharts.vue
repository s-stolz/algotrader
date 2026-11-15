<template>
  <div
    class="replay-charts"
    aria-label="Equity and drawdown charts"
    :data-sampled="sampled"
  >
    <section aria-label="Equity chart">
      <header class="chart-header">
        <div class="chart-title">
          <h2>Equity</h2>
          <n-tag
            v-if="sampled"
            size="small"
            round
            :bordered="false"
            title="At least one compared run uses a sampled curve."
            >Sampled</n-tag
          >
        </div>
        <ReplayLegend
          :series="series"
          :color-for-run="seriesColor"
        />
      </header>
      <div
        class="chart-panel"
        :aria-busy="loading || undefined"
      >
        <ReplayLoading
          v-if="loading"
          overlay
        />
        <div
          ref="equityContainer"
          class="chart"
          data-testid="equity-chart"
        />
      </div>
    </section>
    <section aria-label="Drawdown chart">
      <header class="chart-header">
        <div class="chart-title">
          <h2>Drawdown</h2>
          <n-tag
            v-if="sampled"
            size="small"
            round
            :bordered="false"
            title="At least one compared run uses a sampled curve."
            >Sampled</n-tag
          >
        </div>
        <ReplayLegend
          :series="series"
          :color-for-run="seriesColor"
        />
      </header>
      <div
        class="chart-panel"
        :aria-busy="loading || undefined"
      >
        <ReplayLoading
          v-if="loading"
          overlay
        />
        <div
          ref="drawdownContainer"
          class="chart"
          data-testid="drawdown-chart"
        />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { NTag } from 'naive-ui';
import { onMounted, onUnmounted, ref, watch } from 'vue';
import {
  createChart,
  LineSeries,
  type AutoscaleInfo,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import ReplayLoading from './workspace/comparison/ReplayLoading.vue';
import ReplayLegend from './workspace/comparison/ReplayLegend.vue';
import type { ReplaySeries } from './backtestComparison';
import { designTokens } from '@/design/tokens';
import { whenChartFontReady } from '@/utils/chart/chartFonts';

const props = defineProps<{
  series: ReplaySeries[];
  sampled?: boolean;
  loading?: boolean;
}>();
const equityContainer = ref<HTMLElement | null>(null);
const drawdownContainer = ref<HTMLElement | null>(null);
let equityChart: IChartApi | null = null;
let drawdownChart: IChartApi | null = null;
let resizeObserver: ResizeObserver | null = null;
let cancelFontWait: (() => void) | null = null;

function seriesColor(run: ReplaySeries): string {
  let hash = 0;
  for (const character of run.runId)
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  const hue = run.ordinal == null ? hash % 360 : (run.ordinal * 137.508) % 360;
  const { replaySaturation, replayLightness } = designTokens.chart;
  return `hsl(${hue} ${replaySaturation} ${replayLightness})`;
}

const rendered = new Map<
  string,
  {
    equity: ISeriesApi<'Line'>;
    drawdown: ISeriesApi<'Line'>;
    points: ReplaySeries['points'];
  }
>();

function fitCharts(): void {
  // Compared runs can contribute different timestamps; allow subpixel spacing
  // even when their combined history is wider than the chart's default limit.
  const pointCount = props.series.reduce(
    (count, run) => count + run.points.length,
    0,
  );
  for (const chart of [equityChart, drawdownChart]) {
    chart?.applyOptions({ timeScale: { minBarSpacing: 1 / (pointCount + 1) } });
    chart?.timeScale().fitContent();
  }
}

function render(): void {
  if (!equityChart || !drawdownChart) return;
  let maxDrawdown = 0;
  for (const run of props.series) {
    for (const point of run.points)
      maxDrawdown = Math.max(maxDrawdown, Math.abs(point.drawdown_pct));
  }
  const drawdownPrecision =
    maxDrawdown > 0
      ? Math.min(8, Math.max(2, 2 - Math.floor(Math.log10(maxDrawdown))))
      : 2;
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
      const options = {
        color: seriesColor(run),
        lineWidth: 2 as const,
        title: '',
        priceLineVisible: false,
        lastValueVisible: false,
      };
      series = {
        equity: equityChart.addSeries(LineSeries, options),
        drawdown: drawdownChart.addSeries(LineSeries, {
          ...options,
          autoscaleInfoProvider: (original: () => AutoscaleInfo | null) => {
            const info = original();
            return info?.priceRange
              ? {
                  ...info,
                  priceRange: {
                    minValue: Math.min(info.priceRange.minValue, 0),
                    maxValue: 0,
                  },
                }
              : null;
          },
        }),
        points: [],
      };
      rendered.set(run.runId, series);
    }
    const minMove = 10 ** -drawdownPrecision;
    series.drawdown.applyOptions({
      priceFormat: {
        type: 'custom',
        minMove,
        formatter: (value: number) =>
          `${(Math.abs(value) < minMove / 2 ? 0 : value).toFixed(drawdownPrecision)}%`,
      },
    });
    if (series.points === run.points) continue;
    series.equity.setData(
      run.points.map((point) => ({
        time: Math.floor(point.timestamp_ms / 1000) as UTCTimestamp,
        value: point.equity,
      })),
    );
    series.drawdown.setData(
      run.points.map((point) => ({
        time: Math.floor(point.timestamp_ms / 1000) as UTCTimestamp,
        value: point.drawdown_pct,
      })),
    );
    series.points = run.points;
  }
  fitCharts();
}

function createCharts(): void {
  if (!equityContainer.value || !drawdownContainer.value) return;
  const options = {
    layout: {
      background: { color: designTokens.color.inset },
      textColor: designTokens.color.muted,
      fontFamily: designTokens.font.ui,
      fontSize: Number.parseInt(designTokens.text.secondary),
    },
    grid: {
      vertLines: { visible: false },
      horzLines: { color: designTokens.color.border },
    },
    crosshair: {
      vertLine: {
        color: designTokens.color.muted,
        labelBackgroundColor: designTokens.color.inset,
      },
      horzLine: {
        color: designTokens.color.muted,
        labelBackgroundColor: designTokens.color.inset,
      },
    },
    rightPriceScale: {
      visible: true,
      autoScale: true,
      minimumWidth: 104,
      borderVisible: false,
      scaleMargins: { top: 0.1, bottom: 0.1 },
    },
    timeScale: {
      borderColor: designTokens.color.border,
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 0,
      fixLeftEdge: true,
      fixRightEdge: true,
      lockVisibleTimeRangeOnResize: true,
    },
    handleScroll: false,
    handleScale: false,
    width: equityContainer.value.clientWidth,
    height: 280,
  };
  equityChart = createChart(equityContainer.value, options);
  drawdownChart = createChart(drawdownContainer.value, {
    ...options,
    width: drawdownContainer.value.clientWidth,
    height: 220,
  });
  render();
}
onMounted(() => {
  cancelFontWait = whenChartFontReady(createCharts);
  if (
    typeof ResizeObserver !== 'undefined' &&
    equityContainer.value &&
    drawdownContainer.value
  ) {
    resizeObserver = new ResizeObserver(() => {
      equityChart?.applyOptions({
        width: equityContainer.value?.clientWidth ?? 0,
      });
      drawdownChart?.applyOptions({
        width: drawdownContainer.value?.clientWidth ?? 0,
      });
      fitCharts();
    });
    resizeObserver.observe(equityContainer.value);
    resizeObserver.observe(drawdownContainer.value);
  }
});
watch(() => props.series, render);
onUnmounted(() => {
  cancelFontWait?.();
  resizeObserver?.disconnect();
  equityChart?.remove();
  drawdownChart?.remove();
});
</script>

<style scoped>
.replay-charts {
  min-width: 0;
  width: 100%;
  display: grid;
  gap: var(--design-space-xl);
  margin-top: var(--design-space-lg);
}
.replay-charts section {
  min-width: 0;
}
.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--design-space-md);
  margin-bottom: var(--design-space-md);
}
.chart-title {
  display: flex;
  align-items: center;
  gap: var(--design-space-sm);
}
.chart-header h2 {
  margin: 0;
  font-size: var(--design-text-heading);
  color: var(--design-color-body);
}
.chart-panel {
  position: relative;
  padding: var(--design-space-lg) var(--design-space-md) var(--design-space-sm);
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
  overflow: hidden;
  background: var(--design-color-inset);
}
.chart {
  width: 100%;
  min-width: 0;
}
</style>
