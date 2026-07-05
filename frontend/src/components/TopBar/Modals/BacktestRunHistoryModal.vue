<template>
  <BaseModal ref="baseModal" :modalId="'backtestRuns'" :title="'Backtest Runs'">
    <div class="backtest-run-history">
      <div class="history-filters">
        <n-input
          v-model:value="textFilter"
          data-testid="backtest-run-search"
          autocomplete="off"
          placeholder="Search runs"
          :input-props="{ id: 'backtest-run-search-input' }"
          round
          clearable
        >
          <template #prefix>
            <n-icon>
              <SearchOutline />
            </n-icon>
          </template>
        </n-input>

        <select
          v-model="statusFilter"
          data-testid="backtest-run-status-filter"
          class="status-filter"
          aria-label="Filter Backtest Runs by status"
        >
          <option value="all">All statuses</option>
          <option
            v-for="status in backtestRunStatuses"
            :key="status"
            :value="status"
          >
            {{ status }}
          </option>
        </select>
      </div>

      <p v-if="loadError" class="modal-error">{{ loadError }}</p>
      <p v-if="deleteError" class="modal-error">{{ deleteError }}</p>
      <p v-if="overlayStore.error" class="modal-error">{{ overlayStore.error }}</p>
      <p v-if="isLoading" class="modal-state">Loading Backtest Runs...</p>

      <n-scrollbar style="max-height: 420px">
        <table class="run-table">
          <tbody>
            <tr
              v-for="{ run, selectability, metrics } in filteredRunRows"
              :key="run.run_id"
              class="backtest-run-row"
              :class="{ 'backtest-run-row-disabled': !selectability.selectable }"
              :data-testid="`backtest-run-row-${run.run_id}`"
            >
              <td class="run-main">
                <div class="run-title-line">
                  <span class="run-id">{{ shortRunId(run.run_id) }}</span>
                  <span class="run-status" :class="`run-status-${run.status}`">
                    {{ run.status }}
                  </span>
                </div>
                <div class="run-strategy">{{ run.request.strategy.strategy_id }}</div>
                <div class="run-context">
                  <span>{{ formatSymbols(run) }}</span>
                  <span>{{ formatExchange(run) }}</span>
                  <span>{{ run.request.timeframe }}</span>
                </div>
                <div class="run-timestamps">
                  <span>Submitted {{ formatTimestamp(run.submitted_at_ms) }}</span>
                  <span>Completed {{ formatTimestamp(run.completed_at_ms) }}</span>
                </div>
                <div v-if="metrics.length > 0" class="run-metrics">
                  <span
                    v-for="metric in metrics"
                    :key="`${run.run_id}-${metric}`"
                  >
                    {{ metric }}
                  </span>
                </div>
                <div v-if="run.error_message" class="run-error-message">
                  {{ run.error_message }}
                </div>
              </td>
              <td class="run-actions">
                <p
                  v-if="selectability.reason"
                  class="selectability-reason"
                >
                  {{ selectability.reason }}
                </p>
                <div class="run-action-buttons">
                  <n-button
                    size="small"
                    class="select-run-button"
                    :data-testid="`backtest-run-select-${run.run_id}`"
                    :disabled="!selectability.selectable || overlayStore.isLoading"
                    @click="onSelectRun(run)"
                  >
                    Open
                  </n-button>
                  <n-button
                    text
                    size="small"
                    class="delete-run-button"
                    :data-testid="`backtest-run-delete-${run.run_id}`"
                    :aria-label="`Delete Backtest Run ${run.run_id}`"
                    :title="deleteRunTitle(run)"
                    :disabled="!canDeleteRun(run) || isDeletingRun(run.run_id)"
                    @click="onDeleteRun(run)"
                  >
                    <n-icon size="18">
                      <TrashOutline />
                    </n-icon>
                  </n-button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <p v-if="!isLoading && filteredRunRows.length === 0" class="modal-state">
          No Backtest Runs match the filters.
        </p>
      </n-scrollbar>
    </div>

    <template #footer>
      <n-button @click="closeModal" class="button-close">Close</n-button>
    </template>
  </BaseModal>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { NButton, NIcon, NInput, NScrollbar } from 'naive-ui';

import { deleteBacktestRun, listBacktestRuns } from '@/api/backtesterClient';
import BaseModal from '@/components/Common/BaseModal.vue';
import { SearchOutline, TrashOutline } from '@/icons';
import {
  useBacktestOverlayStore,
  type BacktestRunSelectability,
} from '@/stores/backtestOverlayStore';
import {
  BACKTEST_RUN_STATUSES,
  type BacktestRun,
  type BacktestRunStatus,
} from '@/types/backtesterContracts';
import type { JsonValue } from '@/types/contracts';

defineOptions({
  name: 'BacktestRunHistoryModal',
});

interface BaseModalExpose {
  close: () => void;
}

type StatusFilter = BacktestRunStatus | 'all';

interface BacktestRunRow {
  metrics: string[];
  run: BacktestRun;
  selectability: BacktestRunSelectability;
}

const baseModal = ref<BaseModalExpose | null>(null);
const runs = ref<BacktestRun[]>([]);
const isLoading = ref(false);
const loadError = ref<string | null>(null);
const deleteError = ref<string | null>(null);
const deletingRunIds = ref<ReadonlySet<string>>(new Set());
const textFilter = ref('');
const statusFilter = ref<StatusFilter>('all');
const overlayStore = useBacktestOverlayStore();
const backtestRunStatuses = BACKTEST_RUN_STATUSES;

const filteredRunRows = computed<BacktestRunRow[]>(() => runs.value
  .filter((run) => matchesStatusFilter(run) && matchesTextFilter(run))
  .map((run) => ({
    run,
    metrics: formatMetrics(run),
    selectability: selectabilityFor(run),
  })));

function closeModal(): void {
  baseModal.value?.close();
}

async function loadRuns(): Promise<void> {
  isLoading.value = true;
  loadError.value = null;

  try {
    runs.value = await listBacktestRuns();
  } catch (error) {
    runs.value = [];
    loadError.value = error instanceof Error
      ? error.message
      : 'Failed to fetch Backtest Runs.';
  } finally {
    isLoading.value = false;
  }
}

function matchesStatusFilter(run: BacktestRun): boolean {
  return statusFilter.value === 'all' || run.status === statusFilter.value;
}

function matchesTextFilter(run: BacktestRun): boolean {
  const query = textFilter.value.trim().toLowerCase();

  if (!query) {
    return true;
  }

  return [
    run.run_id,
    run.status,
    run.request.strategy.strategy_id,
    run.request.timeframe,
    run.request.exchange ?? '',
    ...run.request.symbols,
  ].some((value) => value.toLowerCase().includes(query));
}

function selectabilityFor(run: BacktestRun): BacktestRunSelectability {
  return overlayStore.getBacktestRunSelectability(run);
}

function canDeleteRun(run: BacktestRun): boolean {
  return run.status === 'succeeded' || run.status === 'failed';
}

function deleteRunTitle(run: BacktestRun): string {
  if (canDeleteRun(run)) {
    return 'Delete Backtest Run and all trades and fills';
  }

  return 'Only succeeded or failed Backtest Runs can be deleted';
}

function isDeletingRun(runId: string): boolean {
  return deletingRunIds.value.has(runId);
}

function setRunDeleting(runId: string, isDeleting: boolean): void {
  const nextRunIds = new Set(deletingRunIds.value);

  if (isDeleting) {
    nextRunIds.add(runId);
  } else {
    nextRunIds.delete(runId);
  }

  deletingRunIds.value = nextRunIds;
}

async function onSelectRun(run: BacktestRun): Promise<void> {
  const selectability = selectabilityFor(run);

  if (!selectability.selectable) {
    return;
  }

  try {
    const result = await overlayStore.selectRun(run);

    if (result.selectable) {
      closeModal();
    }
  } catch {
    // The overlay store owns the user-facing selection error.
  }
}

async function onDeleteRun(run: BacktestRun): Promise<void> {
  if (!canDeleteRun(run) || isDeletingRun(run.run_id)) {
    return;
  }

  const confirmed = window.confirm(
    `Delete Backtest Run ${shortRunId(run.run_id)} and all trades and fills? This cannot be undone.`,
  );

  if (!confirmed) {
    return;
  }

  setRunDeleting(run.run_id, true);
  deleteError.value = null;

  try {
    await deleteBacktestRun(run.run_id);
    runs.value = runs.value.filter((candidate) => candidate.run_id !== run.run_id);

    if (overlayStore.selectedRunId === run.run_id) {
      overlayStore.clearOverlay();
    }
  } catch (error) {
    deleteError.value = error instanceof Error
      ? error.message
      : 'Failed to delete Backtest Run.';
  } finally {
    setRunDeleting(run.run_id, false);
  }
}

function shortRunId(runId: string): string {
  if (runId.length <= 12) {
    return runId;
  }

  return runId.slice(0, 12);
}

function formatSymbols(run: BacktestRun): string {
  if (run.request.symbols.length === 0) {
    return 'No symbol';
  }

  return run.request.symbols.join(', ');
}

function formatExchange(run: BacktestRun): string {
  return run.request.exchange ?? 'No exchange';
}

function formatTimestamp(timestampMs?: number | null): string {
  if (!timestampMs) {
    return 'pending';
  }

  return new Date(timestampMs).toISOString().replace('T', ' ').replace('.000Z', ' UTC');
}

function formatMetrics(run: BacktestRun): string[] {
  if (!run.metrics) {
    return [];
  }

  const metrics: string[] = [];

  for (const [key, value] of Object.entries(run.metrics)) {
    if (!isDisplayableMetricValue(value)) {
      continue;
    }

    metrics.push(`${key} ${formatMetricValue(value)}`);

    if (metrics.length === 4) {
      break;
    }
  }

  return metrics;
}

function isDisplayableMetricValue(value: JsonValue): value is string | number | boolean {
  return typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean';
}

function formatMetricValue(value: string | number | boolean): string {
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)));
  }

  return String(value);
}

onMounted(() => {
  void loadRuns();
});
</script>

<style scoped>
:deep(.modal) {
  max-width: min(920px, calc(100vw - 32px));
}

.backtest-run-history {
  width: min(860px, calc(100vw - 32px));
  max-width: 100%;
}

.history-filters {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 170px;
  gap: 10px;
  padding: 10px 15px;
  align-items: center;
}

.status-filter {
  height: 34px;
  border: 1px solid #3d4658;
  border-radius: 17px;
  background: #171b26;
  color: #ffffffd1;
  padding: 0 12px;
}

.run-table {
  width: 100%;
  border-collapse: collapse;
}

.backtest-run-row {
  border-top: 1px solid #a0a0a029;
}

.backtest-run-row:hover {
  background-color: #36363661;
}

.backtest-run-row-disabled {
  color: #ffffff99;
}

.run-main,
.run-actions {
  padding: 10px 15px;
  vertical-align: top;
}

.run-main {
  width: 72%;
}

.run-title-line,
.run-context,
.run-timestamps,
.run-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.run-id {
  font-size: 13px;
  color: #ffffff;
}

.run-status {
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 11px;
  text-transform: uppercase;
}

.run-status-succeeded {
  background: #1f6f47;
}

.run-status-running,
.run-status-queued {
  background: #435577;
}

.run-status-failed {
  background: #7a2f3a;
}

.run-strategy {
  margin-top: 5px;
  color: #ffffff;
}

.run-context,
.run-timestamps,
.run-metrics {
  margin-top: 4px;
  font-size: 12px;
  color: #c9d0dc;
}

.run-error-message,
.selectability-reason,
.modal-error {
  color: #ffb4b4;
}

.run-error-message,
.selectability-reason {
  margin: 6px 0 0;
  font-size: 12px;
}

.run-actions {
  text-align: right;
}

.run-action-buttons {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.select-run-button {
  min-width: 64px;
}

.delete-run-button {
  width: 30px;
  height: 30px;
  color: #ffb4b4;
}

.delete-run-button:hover,
.delete-run-button:focus-visible {
  color: #ff7777;
}

.modal-state,
.modal-error {
  margin: 10px 15px;
}

.button-close {
  min-width: 72px;
}

@media (max-width: 760px) {
  .backtest-run-history {
    width: calc(100vw - 32px);
  }

  .history-filters {
    grid-template-columns: 1fr;
  }

  .run-main,
  .run-actions {
    display: block;
    width: auto;
    text-align: left;
  }

  .run-actions {
    padding-top: 0;
  }

  .run-action-buttons {
    justify-content: flex-start;
  }
}
</style>
