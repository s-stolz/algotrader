<script setup lang="ts">
import { computed } from 'vue';
import { NButton } from 'naive-ui';
import { runName } from '../../backtestWorkspaceRuns';
import { periodProfit, formatResult } from './runResults';
import type { BacktestWorkspace } from '../useBacktestWorkspace';
const props = defineProps<{ inspection: BacktestWorkspace['inspection'] }>();
const { currentRows, selectedComparisonIds, tradeResults } = props.inspection;
const months = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
  'Year total',
];
const selected = computed(() =>
  currentRows.value.filter(
    (run) =>
      run.status === 'succeeded' &&
      selectedComparisonIds.value.includes(run.run_id),
  ),
);
const failures = computed(() =>
  currentRows.value.filter(
    (run) => tradeResults.states.value[run.run_id]?.status === 'error',
  ),
);
const rows = computed(() => {
  const years = [
    ...new Set(
      selected.value.flatMap((run) => {
        const first = new Date(run.request.start_ms).getUTCFullYear();
        const last = new Date(run.request.end_ms - 1).getUTCFullYear();
        return Array.from({ length: last - first + 1 }, (_, i) => first + i);
      }),
    ),
  ].sort((a, b) => a - b);
  return years.map((year) => ({
    year,
    cells: months.map((_, month) =>
      selected.value.map((run) => {
        const state = tradeResults.states.value[run.run_id];
        const amount = periodProfit(
          run,
          state?.result,
          year,
          month < 12 ? month : undefined,
        );
        return {
          id: run.run_id,
          name: runName(run),
          amount,
          loading: !state || state.status === 'loading',
          percent:
            amount === null
              ? null
              : (amount / run.request.initial_capital) * 100,
        };
      }),
    ),
  }));
});
</script>
<template>
  <p
    v-if="failures.length"
    role="alert"
    >Trade results unavailable for {{ failures.map(runName).join(', ') }}.
    <n-button
      size="small"
      @click="tradeResults.retry"
      >Retry</n-button
    ></p
  >
  <section
    v-if="selected.length"
    class="calendar-panel"
    aria-label="Monthly and yearly results"
  >
    <h2>Monthly & yearly results</h2>
    <div class="calendar-scroll"
      ><table class="stacked-calendar"
        ><thead
          ><tr
            ><th scope="col">Year</th
            ><th
              v-for="month in months"
              :key="month"
              scope="col"
              >{{ month }}</th
            ></tr
          ></thead
        ><tbody
          ><tr
            v-for="row in rows"
            :key="row.year"
            ><th scope="row">{{ row.year }}</th
            ><td
              v-for="(cell, month) in row.cells"
              :key="month"
              :class="{ 'annual-cell': month === 12 }"
              ><div
                v-for="entry in cell"
                :key="entry.id"
                class="run-result"
                :aria-busy="entry.loading"
                ><span class="run-label">{{ entry.name }}</span
                ><strong
                  :class="
                    entry.amount === null
                      ? ''
                      : entry.amount >= 0
                        ? 'positive'
                        : 'negative'
                  "
                  >{{
                    entry.loading ? '…' : formatResult(entry.amount, 'amount')
                  }}</strong
                ><span class="return-percent">{{
                  entry.loading ? '…' : formatResult(entry.percent, 'percent')
                }}</span></div
              ></td
            ></tr
          ></tbody
        ></table
      ></div
    >
  </section>
</template>
<style scoped>
.calendar-panel {
  margin-top: var(--design-space-xl);
}
.calendar-panel h2 {
  font-size: var(--design-text-heading);
}
.calendar-scroll {
  overflow-x: auto;
  padding: var(--design-space-md);
  background: var(--design-color-inset);
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
}
.positive {
  color: var(--design-color-positive);
}
.negative {
  color: var(--design-color-negative);
}
.stacked-calendar {
  width: 100%;
  min-width: 1350px;
  border-collapse: separate;
  border-spacing: 0;
  font-variant-numeric: tabular-nums;
}
.stacked-calendar th {
  padding: 12px 8px;
  font-weight: 500;
  text-align: left;
  background: var(--design-color-inset);
}
.stacked-calendar th:first-child {
  position: sticky;
  left: 0;
  z-index: 1;
  min-width: 60px;
  vertical-align: top;
}
.stacked-calendar td {
  padding: 0 5px 16px;
  vertical-align: top;
  border-bottom: 1px solid var(--design-color-border);
}
.run-result {
  display: grid;
  width: 100%;
  gap: 3px;
  margin: 4px 0;
  padding: 9px 10px;
  text-align: right;
  font: inherit;
  color: var(--design-color-body);
  background: var(--design-color-panel);
  border: 1px solid transparent;
  border-radius: var(--design-radius-panel);
  box-sizing: border-box;
  cursor: default;
  white-space: nowrap;
}
.run-label {
  text-align: left;
  font-size: var(--design-text-id);
  color: var(--design-color-muted);
}
.run-result strong {
  font-size: var(--design-text-body);
  font-weight: 500;
}
.return-percent {
  font-size: var(--design-text-id);
  color: var(--design-color-muted);
}
.annual-cell {
  border-left: 1px solid var(--design-color-border);
}
.annual-cell .run-result {
  background: var(--design-color-header);
}
.run-result:hover {
  background: var(--design-color-hover);
  border-color: var(--design-color-border);
}
</style>
