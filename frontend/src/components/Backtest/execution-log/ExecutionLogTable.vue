<script setup lang="ts">
import { computed } from 'vue';
import { NButton, NIcon } from 'naive-ui';
import LocateOutline from '@vicons/ionicons5/es/LocateOutline';
import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import {
  executionLogItemKey,
  type ExecutionLogItem,
} from '@/types/backtest/executionLog';
const props = defineProps<{
  items: ExecutionLogItem[];
  currency: string | null;
}>();
const emit = defineEmits<{ jump: [timestampMs: number] }>();
const timeline = computed(() =>
  props.items.map((item) => ({
    key: executionLogItemKey(item),
    timestamp_ms: item.timestamp_ms,
    trade: item.kind === 'trade' ? item.trade : null,
    order: item.kind === 'unexecuted_order' ? item.order : null,
  })),
);
const executionNumber = new Intl.NumberFormat('en-GB', {
  maximumSignificantDigits: 17,
});
function time(value: number) {
  return new Date(value).toLocaleString('en-GB', {
    timeZone: 'UTC',
    year: 'numeric',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}
</script>
<template>
  <BaseDataTable
    class="paired-trades"
    data-testid="execution-trades-table"
    :single-line="false"
    :row-hover="false"
    :scroll-x="780"
  >
    <thead
      ><tr
        ><th>Trade</th><th>Type</th><th>Date and time · UTC</th><th>Price</th
        ><th>Quantity</th
        ><th title="Combined entry and exit fees, in account units"
          >Fees{{ currency ? ` (${currency})` : '' }}</th
        ><th>Realized PnL{{ currency ? ` (${currency})` : '' }}</th></tr
      ></thead
    >
    <tbody
      v-for="row in timeline"
      :key="row.key"
      :class="{ 'unexecuted-order': row.order }"
    >
      <tr v-if="row.order">
        <td
          ><strong class="unexecuted-label">Not executed</strong>
          <span class="direction">{{
            row.order.side === 'buy'
              ? 'Intended buy'
              : row.order.side === 'sell'
                ? 'Intended sell'
                : 'Direction not recorded'
          }}</span>
        </td>
        <td class="leg">Order event</td>
        <td>{{ time(row.timestamp_ms) }}</td>
        <td class="number"
          >{{ row.order.planned_price ?? '—' }}<small>Planned price</small></td
        >
        <td class="number"
          >{{ row.order.planned_quantity ?? '—'
          }}<small>Planned quantity</small></td
        >
        <td class="number">—</td>
        <td
          ><span>{{ row.order.outcome.replaceAll('_', ' ') }}</span
          ><small>No execution / PnL</small></td
        >
      </tr>
      <template v-else-if="row.trade">
        <tr>
          <td rowspan="2"
            ><strong>#{{ row.trade.sequence + 1 }}</strong
            ><span class="direction">{{
              row.trade.trade_direction === 'long' ? '↗ Long' : '↘ Short'
            }}</span
            ><small>{{ row.trade.symbol }}</small></td
          >
          <td class="leg">Exit</td
          ><td
            >{{ time(row.trade.exit_timestamp_ms) }}
            <n-button
              text
              circle
              title="Go to exit"
              aria-label="Go to exit"
              @click="emit('jump', row.trade.exit_timestamp_ms)"
              ><n-icon><LocateOutline /></n-icon></n-button></td
          ><td class="number">{{
            executionNumber.format(row.trade.exit_price)
          }}</td>
          <td
            rowspan="2"
            class="number"
            >{{ executionNumber.format(row.trade.quantity) }}</td
          >
          <td
            rowspan="2"
            class="number"
            title="Combined entry and exit fees"
          >
            {{
              row.trade.fees.toLocaleString('en-GB', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 6,
              })
            }}
          </td>
          <td
            rowspan="2"
            class="number"
            ><strong
              :class="row.trade.realized_pnl >= 0 ? 'positive' : 'negative'"
              >{{ row.trade.realized_pnl > 0 ? '+' : ''
              }}{{ row.trade.realized_pnl.toFixed(2) }}</strong
            ><small>{{ row.trade.exit_reason.replaceAll('_', ' ') }}</small></td
          >
        </tr>
        <tr
          ><td class="leg">Entry</td
          ><td
            >{{ time(row.trade.entry_timestamp_ms) }}
            <n-button
              text
              circle
              title="Go to entry"
              aria-label="Go to entry"
              @click="emit('jump', row.trade.entry_timestamp_ms)"
              ><n-icon><LocateOutline /></n-icon></n-button></td
          ><td
            class="number"
            data-interior-cell
            >{{ executionNumber.format(row.trade.entry_price) }}</td
          ></tr
        >
      </template>
    </tbody>
  </BaseDataTable>
</template>
<style scoped>
th {
  text-align: left;
}
td {
  padding: 13px 18px;
}
strong {
  font-weight: 500;
}
small,
.direction {
  display: block;
  margin-top: 5px;
}
small,
.leg {
  color: var(--design-color-muted);
}
.direction {
  color: var(--design-color-info);
}
.number {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.positive {
  color: var(--design-color-positive);
}
.negative {
  color: var(--design-color-negative);
}
.unexecuted-order td {
  background: color-mix(
    in srgb,
    var(--design-color-warning) 8%,
    var(--design-color-panel)
  );
  color: var(--design-color-muted);
}
.unexecuted-order td:first-child {
  border-left: 3px solid var(--design-color-warning);
}
.unexecuted-label {
  color: var(--design-color-warning);
}
.unexecuted-order .direction {
  color: var(--design-color-muted);
}
</style>
