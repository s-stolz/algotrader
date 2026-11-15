<template>
  <section
    class="parameter-heatmap"
    aria-label="Parameter heatmap"
  >
    <h2>Parameter heatmap</h2>
    <BaseAsyncState
      v-if="adapted.error"
      kind="error"
      label="Heatmap unavailable"
      :message="adapted.error"
    />
    <p v-else-if="axes.length < 2"
      >This Backtest has fewer than two varying numeric parameters.</p
    >
    <template v-else>
      <div class="controls">
        <label
          >X axis<BaseSelect
            v-model:value="x"
            placeholder="Select parameter"
            aria-label="X axis"
            clearable
            :options="
              axes.map((field) => ({
                label: field.label,
                value: field.key,
                disabled: field.key === y,
              }))
            "
        /></label>
        <n-button
          :disabled="!x || !y"
          aria-label="Swap axes"
          @click="swap"
          >⇄</n-button
        >
        <label
          >Y axis<BaseSelect
            v-model:value="y"
            placeholder="Select parameter"
            aria-label="Y axis"
            clearable
            :options="
              axes.map((field) => ({
                label: field.label,
                value: field.key,
                disabled: field.key === x,
              }))
            "
        /></label>
        <label
          >Metric<BaseSelect
            v-model:value="metric"
            placeholder="Select metric"
            aria-label="Metric"
            clearable
            :options="[...heatmapMetrics]"
        /></label>
        <FixedInputsPopover
          :fields="fixedDimensions"
          :values="fixed"
          @change="(key, value) => (fixed[key] = value)"
        />
        <n-button
          v-if="readError"
          size="small"
          circle
          quaternary
          :disabled="pending"
          title="Retry failed reads"
          aria-label="Retry failed reads"
          @click="emit('retry')"
        >
          <template #icon><n-icon :component="RefreshOutline" /></template>
        </n-button>
      </div>
      <p
        v-if="!ready"
        class="prompt"
        >Select X axis, Y axis, and metric.</p
      >
      <HeatmapPlot
        v-else
        :cells="cells"
        :x="xDimension!"
        :y="yDimension!"
        :metric="metric!"
        :bounds="bounds"
        :pending="pending"
        :selected-ids="selectedIds"
        :empty-reason="emptyReason"
        @inspect="(run) => emit('inspect', run)"
      />
    </template>
  </section>
</template>
<script setup lang="ts">
import { toRef } from 'vue';
import { NButton, NIcon } from 'naive-ui';
import RefreshOutline from '@vicons/ionicons5/es/RefreshOutline';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';
import type { Backtest, BacktestRun } from '@/types/backtesterContracts';
import { useParameterHeatmap } from './useParameterHeatmap';
import { heatmapMetrics } from './heatmapMetrics';
import FixedInputsPopover from './FixedInputsPopover.vue';
import { lazyComponent } from '@/components/Common/lazyComponent';
const HeatmapPlot = lazyComponent(() => import('./HeatmapPlot.vue'), 'heatmap');
const props = defineProps<{
  saved: { backtest: Backtest; runs: BacktestRun[] };
  pending: boolean;
  readError: string | null;
  selectedIds: string[];
}>();
const emit = defineEmits<{ retry: []; inspect: [run: BacktestRun] }>();
const {
  x,
  y,
  metric,
  fixed,
  axes,
  fixedDimensions,
  xDimension,
  yDimension,
  ready,
  cells,
  bounds,
  emptyReason,
  adapted,
  swap,
} = useParameterHeatmap(toRef(props, 'saved'));
</script>
<style scoped>
.parameter-heatmap {
  border-top: 1px solid var(--design-color-border);
  padding-top: var(--design-space-xl);
  margin-top: var(--design-space-xl);
}
h2 {
  margin: 0 0 var(--design-space-xl);
  font-size: var(--design-text-heading);
  font-weight: 600;
}
.controls {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--design-space-md);
}
.controls label {
  display: flex;
  flex-direction: column;
  gap: var(--design-space-sm);
  width: 180px;
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
.prompt {
  color: var(--design-color-muted);
  padding: var(--design-space-xl) 0;
}
</style>
