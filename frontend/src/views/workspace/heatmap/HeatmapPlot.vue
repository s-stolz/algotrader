<template>
  <div>
    <div class="plot-status">
      <n-spin
        v-if="pending"
        :size="20"
        role="status"
        aria-label="Loading heatmap results"
      />
      <span
        v-if="emptyReason"
        tabindex="0"
        :title="emptyReason"
        :aria-label="emptyReason"
        >ⓘ</span
      >
    </div>
    <VChart
      v-if="fontReady"
      class="chart"
      :option="options"
      autoresize
      @click="chartClick"
    />
    <div
      v-if="!pending && bounds"
      class="scale"
      :aria-label="`${metricLabel} scale`"
    >
      <span>{{
        formatMetric(
          metric === 'drawdown' ? bounds[1] : bounds[0],
          metric,
          true,
        )
      }}</span>
      <span
        class="gradient"
        aria-hidden="true"
      />
      <span v-if="bounds[0] !== bounds[1]">{{
        formatMetric(
          metric === 'drawdown' ? bounds[0] : bounds[1],
          metric,
          true,
        )
      }}</span>
    </div>
    <div class="state-key">
      <span v-if="!pending && hasInfinity">∞ Profit factor</span>
      <span
        v-for="state in specialStates"
        :key="state.label"
        ><i :style="{ background: state.color }">{{ state.symbol }}</i
        >{{ state.label }}</span
      >
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';
import { whenChartFontReady } from '@/utils/chart/chartFonts';
import { NSpin } from 'naive-ui';
import { use } from 'echarts/core';
import { HeatmapChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
  AriaComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import VChart from 'vue-echarts';
import type { BacktestRun } from '@/types/backtesterContracts';
import type { HeatmapDimension } from '@/types/backtest/heatmapSnapshot';
import type { HeatmapCell } from './heatmapGrid';
import { heatmapChart, specialStates } from './heatmapChart';
import {
  formatMetric,
  heatmapMetrics,
  type HeatmapMetric,
} from './heatmapMetrics';
use([
  HeatmapChart,
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
  AriaComponent,
  CanvasRenderer,
]);
const props = defineProps<{
  cells: HeatmapCell[];
  x: HeatmapDimension;
  y: HeatmapDimension;
  metric: HeatmapMetric;
  bounds: [number, number] | null;
  pending: boolean;
  selectedIds: string[];
  emptyReason: string | null;
}>();
const fontReady = ref(false);
let cancelFontWait: (() => void) | undefined;
onMounted(() => {
  cancelFontWait = whenChartFontReady(() => {
    fontReady.value = true;
  });
});
onBeforeUnmount(() => cancelFontWait?.());
const emit = defineEmits<{ inspect: [run: BacktestRun] }>();
const options = computed(() =>
  heatmapChart(
    props.cells,
    props.x,
    props.y,
    props.metric,
    props.bounds,
    props.pending,
    props.selectedIds,
  ),
);
const metricLabel = computed(
  () => heatmapMetrics.find((entry) => entry.value === props.metric)?.label,
);
const hasInfinity = computed(() =>
  props.cells.some((cell) => cell.value === Infinity),
);
function chartClick(event: { data?: unknown }) {
  const data = event.data as { cell?: HeatmapCell } | undefined;
  if (data?.cell?.run) emit('inspect', data.cell.run);
}
</script>
<style scoped>
.chart {
  height: 400px;
  width: 100%;
}
.plot-status {
  display: flex;
  align-items: center;
  gap: var(--design-space-sm);
  min-height: 24px;
}
.scale {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--design-space-md);
  font-size: var(--design-text-secondary);
}
.gradient {
  width: 160px;
  height: 10px;
  background: linear-gradient(
    90deg,
    var(--design-chart-heatmap-worst),
    var(--design-chart-heatmap-midpoint),
    var(--design-chart-heatmap-best)
  );
}
.state-key {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--design-space-lg);
  margin-top: var(--design-space-lg);
  font-size: var(--design-text-secondary);
  color: var(--design-color-muted);
}
.state-key span {
  display: inline-flex;
  align-items: center;
  gap: var(--design-space-sm);
}
i {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  font-style: normal;
  color: var(--design-chart-heatmap-symbol);
}
</style>
