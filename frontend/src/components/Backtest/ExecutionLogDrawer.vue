<template>
  <BaseDrawer :show="show" placement="right" :width="drawerWidth" @update:show="close">
    <n-drawer-content :title="`Execution log · ${runName(run)}`" closable>
      <div class="log-content" data-testid="execution-log-drawer">
        <div class="run-identity"><span>Run ID</span><code>{{ run.run_id }}</code></div>
        <p v-if="run.status !== 'succeeded'" role="status">
          This {{ run.status }} run has no completed execution log.
        </p>
        <p v-else-if="run.result_schema_version !== BACKTEST_RESULT_SCHEMA_VERSION" role="status">
          A completed execution log is unavailable for this result schema.
        </p>
        <template v-else>
          <p v-if="loading" role="status">Loading execution log…</p>
          <p v-else-if="error" role="alert">Execution log unavailable. {{ error }}</p>
          <template v-else-if="trades !== null && fills !== null">
            <p v-if="trades.length === 0 && fills.length === 0" role="status">
              This successful run has no executions.
            </p>
            <template v-else>
              <div class="log-toolbar">
                <n-tabs v-model:value="tab" type="line" size="small" aria-label="Execution records">
                  <n-tab name="trades" data-testid="execution-trades-tab">
                    Closed Trades ({{ trades.length }})
                  </n-tab>
                  <n-tab name="fills" data-testid="execution-fills-tab">
                    Fills ({{ fills.length }})
                  </n-tab>
                </n-tabs>
                <div v-if="tab === 'trades'" class="log-filters">
                  <div class="log-filter">
                    <span id="execution-direction-label">Trade direction</span>
                    <n-select
                      v-model:value="direction"
                      data-testid="execution-direction"
                      aria-labelledby="execution-direction-label"
                      :options="directionOptions"
                    />
                  </div>
                  <div class="log-filter">
                    <span id="execution-exit-reason-label">Exit reason</span>
                    <n-select
                      v-model:value="exitReason"
                      data-testid="execution-exit-reason"
                      aria-labelledby="execution-exit-reason-label"
                      :options="exitReasonOptions"
                    />
                  </div>
                </div>
              </div>
              <p v-if="activeRecords.length === 0" role="status">
                <template v-if="activeTotal === 0">
                  No {{ tab === 'trades' ? 'Closed Trades' : 'Fills' }} in this run.
                </template>
                <template v-else>
                  No {{ tab === 'trades' ? 'Closed Trades' : 'Fills' }} match these filters.
                </template>
              </p>
              <div v-else class="table-scroll" role="tabpanel" :aria-label="tab === 'trades' ? 'Closed Trades' : 'Fills'">
                <BaseDataTable
                  v-if="tab === 'trades'"
                  data-testid="execution-trades-table"
                  :columns="tradeColumns"
                  :data="filteredTrades"
                  :row-key="(trade: BacktestClosedTrade) => trade.sequence"
                  :scroll-x="2200"
                  max-height="min(60vh, 560px)"
                  striped
                />
                <BaseDataTable
                  v-else
                  data-testid="execution-fills-table"
                  :columns="fillColumns"
                  :data="fills"
                  :row-key="(fill: BacktestFill) => fill.sequence"
                  :scroll-x="900"
                  max-height="min(60vh, 560px)"
                  striped
                />
              </div>
            </template>
          </template>
        </template>
      </div>
    </n-drawer-content>
  </BaseDrawer>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import { NDrawerContent, NSelect, NTab, NTabs, type DataTableColumns } from 'naive-ui';

import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import BaseDrawer from '@/components/Common/BaseDrawer.vue';
import { fetchBacktestClosedTrades, fetchBacktestFills } from '@/api/backtesterClient';
import {
  BACKTEST_RESULT_SCHEMA_VERSION, type BacktestClosedTrade, type BacktestFill, type BacktestRun,
} from '@/types/backtesterContracts';
import { formatSigned, runName } from '@/views/backtestWorkspaceRuns';

const props = defineProps<{ run: BacktestRun; show: boolean }>();
const emit = defineEmits<{ close: [] }>();
const drawerWidth = 'min(92vw, 950px)';
const trades = ref<BacktestClosedTrade[] | null>(null);
const fills = ref<BacktestFill[] | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const tab = ref<'trades' | 'fills'>('trades');
const direction = ref('all');
const exitReason = ref('all');
let generation = 0;

watch([() => props.run.run_id, () => props.run.status,
  () => props.run.result_schema_version, () => props.show], () => {
  const current = ++generation;
  trades.value = null;
  fills.value = null;
  error.value = null;
  loading.value = false;
  tab.value = 'trades';
  direction.value = 'all';
  exitReason.value = 'all';
  if (!props.show || props.run.status !== 'succeeded' ||
      props.run.result_schema_version !== BACKTEST_RESULT_SCHEMA_VERSION) return;
  loading.value = true;
  Promise.all([
    fetchBacktestClosedTrades(props.run.run_id), fetchBacktestFills(props.run.run_id),
  ]).then(([closedTrades, runFills]) => {
    if (current !== generation) return;
    trades.value = closedTrades;
    fills.value = runFills;
  }).catch((reason: unknown) => {
    if (current !== generation) return;
    error.value = reason instanceof Error ? reason.message : 'The service could not be read.';
  }).finally(() => {
    if (current === generation) loading.value = false;
  });
}, { immediate: true });

onUnmounted(() => { ++generation; });

const directionOptions = [
  { label: 'All directions', value: 'all' },
  { label: 'Long', value: 'long' },
  { label: 'Short', value: 'short' },
];
const exitReasonOptions = [
  { label: 'All reasons', value: 'all' },
  { label: 'Signal', value: 'signal' },
  { label: 'Stop loss', value: 'stop_loss' },
  { label: 'Take profit', value: 'take_profit' },
];
const filteredTrades = computed(() => (trades.value ?? []).filter((trade) =>
  (direction.value === 'all' || trade.trade_direction === direction.value) &&
  (exitReason.value === 'all' || trade.exit_reason === exitReason.value),
));
const activeRecords = computed(() => tab.value === 'trades' ? filteredTrades.value : fills.value ?? []);
const activeTotal = computed(() => tab.value === 'trades' ? trades.value?.length : fills.value?.length);

const tradeColumns: DataTableColumns<BacktestClosedTrade> = [
  { title: 'Sequence', key: 'sequence', width: 100 },
  { title: 'Trade Direction', key: 'trade_direction', width: 140 },
  { title: 'Entry time (UTC)', key: 'entry_timestamp_ms', width: 250,
    render: (trade) => formatTimestamp(trade.entry_timestamp_ms) },
  { title: 'Entry price', key: 'entry_price', width: 120 },
  { title: 'Exit time (UTC)', key: 'exit_timestamp_ms', width: 250,
    render: (trade) => formatTimestamp(trade.exit_timestamp_ms) },
  { title: 'Exit price', key: 'exit_price', width: 120 },
  { title: 'Quantity', key: 'quantity', width: 100 },
  { title: 'Realized PnL (account units)', key: 'realized_pnl', width: 230,
    render: (trade) => signed(trade.realized_pnl) },
  { title: 'Fees (account units)', key: 'fees', width: 180 },
  { title: 'Exit reason', key: 'exit_reason', width: 140,
    render: (trade) => reasonLabel(trade.exit_reason) },
  { title: 'Planned stop loss', key: 'stop_loss_price', width: 170,
    render: (trade) => trade.stop_loss_price ?? '—' },
  { title: 'Planned take profit', key: 'take_profit_price', width: 180,
    render: (trade) => trade.take_profit_price ?? '—' },
];
const fillColumns: DataTableColumns<BacktestFill> = [
  { title: 'Sequence', key: 'sequence', width: 100 },
  { title: 'Time (UTC)', key: 'timestamp_ms', width: 250,
    render: (fill) => formatTimestamp(fill.timestamp_ms) },
  { title: 'Side', key: 'side', width: 100 },
  { title: 'Quantity', key: 'quantity', width: 120 },
  { title: 'Price', key: 'price', width: 120 },
  { title: 'Fee (account units)', key: 'fees', width: 180 },
];

const timestampFormatter = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit', month: 'short', year: 'numeric',
  hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'UTC',
});
function formatTimestamp(timestampMs: number): string { return timestampFormatter.format(timestampMs); }
function signed(value: number): string { return formatSigned(value); }
function reasonLabel(reason: string): string { return reason.replaceAll('_', ' '); }
function close(): void { emit('close'); }
</script>

<style scoped>
.log-content { display: flex; flex-direction: column; gap: 20px; }
.run-identity { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 12px; color: #8d9fae; font-size: 12px; }
.run-identity span { font-weight: 500; }
.run-identity code { min-width: 0; overflow-wrap: anywhere; font-size: 12px; }
.log-toolbar { padding: 0 18px 18px; border: 1px solid #2b3541; border-radius: 10px; background: #1a2029; }
.log-filters { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; padding-top: 18px; }
.log-filter { display: flex; flex-direction: column; gap: 8px; min-width: 0; color: #9bafbe; font-size: 12px; font-weight: 500; }
.table-scroll { min-width: 0; }
@media (max-width: 600px) {
  .log-toolbar { padding: 0 14px 14px; }
  .log-filters { grid-template-columns: 1fr; gap: 12px; padding-top: 14px; }
}
</style>
