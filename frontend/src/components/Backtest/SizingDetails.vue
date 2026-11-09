<script setup lang="ts">
import { computed } from 'vue';
import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import type { BacktestRun } from '@/types/backtesterContracts';
import { isRecord } from '@/types/transportValues';
const props = defineProps<{ run: BacktestRun }>();
const rows = computed<Array<Record<string, unknown> & { index: number }>>(
  () => {
    const events = props.run.diagnostics?.order_events;
    return Array.isArray(events)
      ? events.flatMap((event, index) =>
          isRecord(event) ? [{ ...event, index }] : [],
        )
      : [];
  },
);
const columns = [
  {
    title: 'Time (UTC)',
    key: 'timestamp_ms',
    render: (row: Record<string, unknown>) =>
      new Date(Number(row.timestamp_ms)).toISOString(),
  },
  { title: 'Order', key: 'order_id' },
  { title: 'Outcome', key: 'outcome' },
  { title: 'Sizing mode', key: 'mode' },
  { title: 'Equity used', key: 'equity' },
  { title: 'Budget', key: 'requested_budget' },
  { title: 'Entry estimate', key: 'entry_price' },
  { title: 'Initial stop', key: 'stop_price' },
  { title: 'Requested quantity', key: 'requested_quantity' },
  { title: 'Rounded quantity', key: 'quantity' },
  { title: 'Planned risk', key: 'planned_risk' },
  { title: 'Fill price', key: 'fill_price' },
  { title: 'Risk at fill', key: 'risk_at_fill' },
  { title: 'Risk difference', key: 'risk_difference' },
  { title: 'Reason', key: 'reason' },
];
const depleted = computed(() =>
  rows.value.some((row) => row.outcome === 'account_depleted'),
);
</script>
<template>
  <section v-if="run.request.execution.sizing">
    <p
      v-if="depleted"
      role="status"
      >Account depleted. Pending orders were cancelled and remaining positions
      closed.</p
    >
    <p v-if="run.request.instrument"
      >Amounts in {{ run.request.instrument.settlement_currency }}. Planned risk
      excludes costs and can differ from actual losses.</p
    >
    <details v-if="rows.length">
      <summary>Sizing decisions and order events</summary>
      <BaseDataTable
        :columns="columns"
        :data="rows"
        :row-key="(row) => row.index"
        :scroll-x="1800"
        :max-height="400"
        striped
      />
    </details>
  </section>
</template>
