<template>
  <n-drawer :show="show" placement="right" :width="drawerWidth" @update:show="close">
    <n-drawer-content :title="`Execution log · ${runName(run)}`" closable>
      <div class="log-content" data-testid="execution-log-drawer">
        <p class="run-identity">{{ run.run_id }}</p>
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
              <div class="tabs" role="tablist" aria-label="Execution records">
                <button
                  type="button"
                  role="tab"
                  data-testid="execution-trades-tab"
                  :aria-selected="tab === 'trades'"
                  @click="tab = 'trades'"
                >
                  Closed Trades ({{ trades.length }})
                </button>
                <button
                  type="button"
                  role="tab"
                  data-testid="execution-fills-tab"
                  :aria-selected="tab === 'fills'"
                  @click="tab = 'fills'"
                >
                  Fills ({{ fills.length }})
                </button>
              </div>
              <div class="log-filters">
                <label>
                  Search {{ tab === 'trades' ? 'Closed Trades' : 'Fills' }}
                  <input v-model="search" data-testid="execution-search" type="search" />
                </label>
                <template v-if="tab === 'trades'">
                  <label>
                    Trade Direction
                    <select v-model="direction" data-testid="execution-direction">
                      <option value="all">All directions</option>
                      <option value="long">Long</option>
                      <option value="short">Short</option>
                    </select>
                  </label>
                  <label>
                    Exit reason
                    <select v-model="exitReason" data-testid="execution-exit-reason">
                      <option value="all">All reasons</option>
                      <option value="signal">Signal</option>
                      <option value="stop_loss">Stop loss</option>
                      <option value="take_profit">Take profit</option>
                    </select>
                  </label>
                </template>
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
                <table v-if="tab === 'trades'" data-testid="execution-trades-table">
                  <thead><tr>
                    <th>Sequence</th><th>Trade Direction</th><th>Entry time (UTC)</th>
                    <th>Entry price</th><th>Exit time (UTC)</th><th>Exit price</th>
                    <th>Quantity</th><th>Realized PnL (account units)</th><th>Fees (account units)</th>
                    <th>Exit reason</th><th>Planned stop loss</th><th>Planned take profit</th>
                  </tr></thead>
                  <tbody><tr v-for="trade in filteredTrades" :key="trade.sequence">
                    <td>{{ trade.sequence }}</td><td>{{ trade.trade_direction }}</td>
                    <td>{{ utc(trade.entry_timestamp_ms) }}</td><td>{{ trade.entry_price }}</td>
                    <td>{{ utc(trade.exit_timestamp_ms) }}</td><td>{{ trade.exit_price }}</td>
                    <td>{{ trade.quantity }}</td><td>{{ signed(trade.realized_pnl) }}</td>
                    <td>{{ trade.fees }}</td><td>{{ reasonLabel(trade.exit_reason) }}</td>
                    <td>{{ trade.stop_loss_price ?? '—' }}</td>
                    <td>{{ trade.take_profit_price ?? '—' }}</td>
                  </tr></tbody>
                </table>
                <table v-else data-testid="execution-fills-table">
                  <thead><tr><th>Sequence</th><th>Time (UTC)</th><th>Side</th>
                    <th>Quantity</th><th>Price</th><th>Fee (account units)</th></tr></thead>
                  <tbody><tr v-for="fill in filteredFills" :key="fill.sequence">
                    <td>{{ fill.sequence }}</td><td>{{ utc(fill.timestamp_ms) }}</td>
                    <td>{{ fill.side }}</td><td>{{ fill.quantity }}</td>
                    <td>{{ fill.price }}</td><td>{{ fill.fees }}</td>
                  </tr></tbody>
                </table>
              </div>
            </template>
          </template>
        </template>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import { NDrawer, NDrawerContent } from 'naive-ui';

import { fetchBacktestClosedTrades, fetchBacktestFills } from '@/api/backtesterClient';
import {
  BACKTEST_RESULT_SCHEMA_VERSION, type BacktestClosedTrade, type BacktestFill, type BacktestRun,
} from '@/types/backtesterContracts';
import { runName } from '@/views/backtestWorkspaceRuns';

const props = defineProps<{ run: BacktestRun; show: boolean }>();
const emit = defineEmits<{ close: [] }>();
const drawerWidth = 'min(92vw, 950px)';
const trades = ref<BacktestClosedTrade[] | null>(null);
const fills = ref<BacktestFill[] | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const tab = ref<'trades' | 'fills'>('trades');
const search = ref('');
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
  search.value = '';
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

const filteredTrades = computed(() => (trades.value ?? []).filter((trade) =>
  (direction.value === 'all' || trade.trade_direction === direction.value) &&
  (exitReason.value === 'all' || trade.exit_reason === exitReason.value) &&
  (!search.value.trim() || [trade.sequence, trade.trade_id, trade.symbol,
    trade.trade_direction, trade.entry_timestamp_ms, trade.exit_timestamp_ms,
    trade.entry_price, trade.exit_price, trade.quantity, trade.realized_pnl, trade.fees,
    trade.exit_reason, trade.stop_loss_price, trade.take_profit_price,
    utc(trade.entry_timestamp_ms), utc(trade.exit_timestamp_ms)]
    .some((value) => String(value ?? '').toLowerCase().includes(search.value.trim().toLowerCase()))),
));
const filteredFills = computed(() => (fills.value ?? []).filter((fill) =>
  !search.value.trim() || [fill.sequence, fill.timestamp_ms, fill.symbol, fill.side,
    fill.quantity, fill.price, fill.fees, utc(fill.timestamp_ms)]
    .some((value) => String(value).toLowerCase().includes(search.value.trim().toLowerCase())),
));
const activeRecords = computed(() => tab.value === 'trades' ? filteredTrades.value : filteredFills.value);
const activeTotal = computed(() => tab.value === 'trades' ? trades.value?.length : fills.value?.length);

function utc(timestampMs: number): string { return new Date(timestampMs).toISOString(); }
function signed(value: number): string { return `${value > 0 ? '+' : ''}${value}`; }
function reasonLabel(reason: string): string { return reason.replaceAll('_', ' '); }
function close(): void { emit('close'); }
</script>

<style scoped>
.run-identity { color: #aeb8c8; overflow-wrap: anywhere; }
.tabs, .log-filters { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; }
.tabs button { padding: 8px 12px; cursor: pointer; }
.tabs button[aria-selected="true"] { border-color: #57d5d0; color: #57d5d0; }
.log-filters label { display: flex; flex-direction: column; gap: 4px; }
.log-filters input, .log-filters select { min-width: 150px; padding: 6px; }
.table-scroll { max-height: min(60vh, 560px); overflow: auto; }
table { border-collapse: collapse; min-width: 100%; white-space: nowrap; }
th, td { padding: 8px 12px; border-bottom: 1px solid #4b5261; text-align: left; }
th { position: sticky; top: 0; background: #252b36; }
</style>
