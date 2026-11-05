<template>
  <section
    v-if="visible"
    class="floating-pill"
    aria-label="Backtest queue"
    data-testid="workspace-queue"
  >
    <BasePopover
      v-model:show="expanded"
      trigger="click"
      placement="top-end"
      :show-arrow="false"
      :width="380"
      :style="{ maxWidth: 'calc(100vw - 32px)' }"
    >
      <template #trigger>
        <button
          ref="trigger"
          class="status-pill"
          :class="{ 'pill-warning': isUnknown || needsAttention }"
          :aria-expanded="expanded"
          :aria-controls="panelId"
          :aria-label="`Backtest activity: ${pillStatus}, ${waitingLabel}`"
          data-testid="queue-toggle"
          @keydown.esc.stop="close"
        >
          <span
            class="status-dot"
            :class="{
              muted: isUnknown || !snapshot?.active_run,
              amber: needsAttention && !isUnknown,
            }"
          />
          <strong>{{ pillStatus }}</strong
          ><span class="pill-divider" />
          <span class="secondary">{{ waitingLabel }}</span>
          <n-icon
            class="pill-chevron"
            :class="{ 'is-expanded': expanded }"
            :size="16"
            aria-hidden="true"
            ><ChevronUpOutline
          /></n-icon>
        </button>
      </template>
      <section
        :id="panelId"
        class="activity-panel"
        aria-label="Backtest activity details"
        @keydown.esc.stop="close"
      >
        <div class="list-heading"
          ><h3>Experiments</h3
          ><n-button
            text
            aria-label="Close activity details"
            @click="close"
            ><n-icon :size="16"><CloseOutline /></n-icon></n-button
        ></div>
        <n-skeleton
          v-if="!snapshot && !readError"
          text
          :repeat="2"
          aria-label="Loading backtest activity"
        />
        <n-alert
          v-if="isUnknown"
          type="warning"
          class="activity-alert"
          data-testid="workspace-queue-unknown"
        >
          {{
            readError
              ? `Activity unavailable: ${readError}`
              : 'Activity status unknown: latest snapshot is old.'
          }}
          <template v-if="snapshot"> Showing last known activity.</template>
          <n-button
            size="small"
            @click="refresh()"
            >Retry</n-button
          >
        </n-alert>
        <template v-if="snapshot">
          <n-alert
            v-if="needsAttention"
            type="warning"
            class="activity-alert"
            data-testid="workspace-worker-status"
            >{{ isUnknown ? 'Last known worker status' : 'Worker' }}:
            {{ snapshot.availability }}. Waiting work may not start.</n-alert
          >
          <n-alert
            v-for="fault in snapshot.operational_faults"
            :key="fault.code"
            type="error"
            class="activity-alert"
            :title="fault.message"
            ><code>{{ fault.code }}</code></n-alert
          >
          <div
            class="active-run"
            data-testid="workspace-queue-active-section"
          >
            <span class="eyebrow">{{
              isUnknown ? 'Last known running' : 'Running'
            }}</span>
            <button
              v-if="snapshot.active_run"
              class="experiment-entry"
              data-testid="queue-view-active"
              @click="inspect(snapshot.active_run.backtest_id)"
            >
              <strong data-testid="workspace-queue-active"
                >{{ activeName }} →</strong
              >
              <span
                class="secondary"
                v-if="activeBacktest"
                >{{ activeBacktest.settled_count }} /
                {{ activeBacktest.total_count }} finished<template
                  v-if="activeBacktest.outcome_counts.failed"
                >
                  · {{ activeBacktest.outcome_counts.failed }} failed</template
                ></span
              >
              <span class="secondary"
                >{{ isUnknown ? 'Started' : 'Active for' }}
                {{ elapsed(snapshot.active_run.started_at_ms)
                }}{{ isUnknown ? ' ago' : '' }}</span
              >
              <progress
                v-if="activeBacktest"
                :value="activeBacktest.settled_count"
                :max="activeBacktest.total_count"
                aria-label="Finished runs"
              />
              <small
                >{{
                  isUnknown ? 'Last known running' : 'Currently running'
                }}
                #{{ (snapshot.active_run.run_ordinal ?? 0) + 1 }}</small
              >
            </button>
            <p
              v-else
              class="secondary"
              data-testid="workspace-queue-no-active"
              >{{
                isUnknown
                  ? 'Last known active run: none'
                  : 'No backtests running'
              }}</p
            >
          </div>
          <span class="eyebrow"
            >{{ isUnknown ? 'Last known queue' : 'Waiting' }} ·
            {{ snapshot.queued.length }}</span
          >
          <ol
            v-if="snapshot.queued.length"
            aria-label="Waiting backtests"
          >
            <li
              v-for="entry in snapshot.queued"
              :key="`${entry.backtest_id}`"
              :data-testid="entryTestId(entry)"
            >
              <button
                class="experiment-entry"
                @click="inspect(entry.backtest_id)"
              >
                <strong>{{ experimentName(entry.backtest_id) }} →</strong>
                <small
                  >{{
                    Object.values(entry.outcome_counts).reduce(
                      (sum, count) => sum + count,
                      0,
                    )
                  }}
                  runs ·
                  {{ finishedCount(entry.outcome_counts) }} finished<template
                    v-if="entry.outcome_counts.failed"
                  >
                    · {{ entry.outcome_counts.failed }} failed</template
                  ></small
                >
                <small>waiting {{ elapsed(entry.submitted_at_ms) }}</small>
              </button>
            </li>
          </ol>
          <p
            v-else
            class="secondary"
            data-testid="workspace-queue-empty"
            >{{
              isUnknown
                ? 'Last known queue had no waiting work.'
                : 'No waiting work.'
            }}</p
          >
          <template v-if="recentExperiments.length">
            <span class="eyebrow">Recently finished</span>
            <ol aria-label="Recently finished experiments">
              <li
                v-for="entry in recentExperiments"
                :key="entry.id"
              >
                <button
                  class="experiment-entry"
                  @click="inspect(entry.id)"
                >
                  <strong>{{ experimentName(entry.id) }} →</strong>
                  <small>{{ entry.summary }}</small>
                </button>
              </li>
            </ol>
          </template>
        </template>
      </section>
    </BasePopover>
  </section>
</template>

<script setup lang="ts">
import { NAlert, NButton, NIcon, NSkeleton } from 'naive-ui';
import { ChevronUpOutline, CloseOutline } from '@vicons/ionicons5';
import {
  computed,
  onActivated,
  onDeactivated,
  onMounted,
  onUnmounted,
  ref,
  useId,
} from 'vue';
import BasePopover from '@/components/Common/BasePopover.vue';
import { useBacktestQueueHealth } from './useBacktestQueueHealth';
import type { Backtest, BacktestQueueEntry } from '@/types/backtesterContracts';
import { backtestName } from '@/views/backtestWorkspaceRuns';

const props = defineProps<{
  backtests?: Backtest[] | null;
}>();
const emit = defineEmits<{ inspect: [id: string] }>();
const expanded = ref(false);
const visible = ref(true);
const trigger = ref<HTMLButtonElement | null>(null);
const panelId = useId();
const { snapshot, readError, nowMs, isUnknown, elapsed, refresh } =
  useBacktestQueueHealth();
const needsAttention = computed(
  () =>
    snapshot.value !== null &&
    (snapshot.value.availability !== 'healthy' ||
      snapshot.value.operational_faults.length > 0),
);
const pillStatus = computed(() =>
  isUnknown.value
    ? 'Status unknown'
    : !snapshot.value
      ? 'Connecting'
      : needsAttention.value
        ? 'Needs attention'
        : snapshot.value.active_run
          ? '1 running'
          : 'Idle',
);
const waitingLabel = computed(() =>
  !snapshot.value
    ? 'Queue unknown'
    : `${isUnknown.value ? 'Last known: ' : ''}${snapshot.value.queued.length} waiting`,
);
const activeName = computed(() => {
  const active = snapshot.value?.active_run;
  return active ? experimentName(active.backtest_id) : '';
});
const activeBacktest = computed(() =>
  props.backtests?.find(
    (backtest) =>
      backtest.backtest_id === snapshot.value?.active_run?.backtest_id,
  ),
);
function finishedCount(counts: Backtest['outcome_counts']): number {
  return counts.succeeded + counts.failed + counts.cancelled;
}
const recentExperiments = computed(() => {
  const entries = [
    ...(props.backtests ?? [])
      .filter((backtest) =>
        ['completed', 'cancelled'].includes(backtest.status),
      )
      .map((backtest) => ({
        id: backtest.backtest_id,
        completedAt: backtest.completed_at_ms,
        summary: `${backtest.settled_count} / ${backtest.total_count} finished · ${
          backtest.status === 'cancelled' ? 'Cancelled' : 'Completed'
        }${backtest.outcome_counts.failed ? ` · ${backtest.outcome_counts.failed} failed` : ''}`,
      })),
  ];
  // Keep fast runs discoverable after they leave the active queue.
  return entries
    .filter(
      (entry) =>
        entry.completedAt != null &&
        nowMs.value - entry.completedAt < 60_000 &&
        entry.completedAt <= nowMs.value &&
        snapshot.value?.active_run?.backtest_id !== entry.id &&
        !snapshot.value?.queued.some(
          (queued) => queued.backtest_id === entry.id,
        ),
    )
    .sort((a, b) => b.completedAt! - a.completedAt!)
    .slice(0, 3);
});
function experimentName(id: string): string {
  const backtest = props.backtests?.find((item) => item.backtest_id === id);
  return backtest ? backtestName(backtest) : `Backtest ${id}`;
}
function entryTestId(entry: BacktestQueueEntry): string {
  return `workspace-queue-backtest-${entry.backtest_id}`;
}
function close(): void {
  expanded.value = false;
  trigger.value?.focus();
}
function inspect(id: string): void {
  close();
  emit('inspect', id);
}
function show(): void {
  visible.value = true;
}
function hide(): void {
  visible.value = false;
  expanded.value = false;
}
defineExpose({ refresh });
onMounted(show);
onActivated(show);
onDeactivated(hide);
onUnmounted(hide);
</script>

<style scoped src="./backtestQueueHealth.css"></style>
