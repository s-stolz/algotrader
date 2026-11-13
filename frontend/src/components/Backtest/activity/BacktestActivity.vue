<script setup lang="ts">
import {
  computed,
  onActivated,
  onDeactivated,
  onMounted,
  onUnmounted,
  ref,
  useId,
  watch,
} from 'vue';
import { NButton, NSpin } from 'naive-ui';
import BasePopover from '@/components/Common/BasePopover.vue';
import { useBacktestActivity } from './useBacktestActivity';
import { activityRows } from './backtestActivityRows';

const emit = defineEmits<{ inspect: [id: string] }>();
const expanded = ref(false);
const visible = ref(true);
const trigger = ref<HTMLButtonElement | null>(null);
const panelId = useId();
const {
  snapshot,
  backtests,
  readError,
  connected,
  isUnknown,
  isRefreshing,
  refresh,
} = useBacktestActivity();
const health = computed(() => {
  if (!connected.value)
    return {
      tone: 'warning',
      label: 'Connection lost',
      message:
        'Live updates are disconnected. Worker status can’t be confirmed.',
    };
  if (readError.value)
    return {
      tone: 'warning',
      label: 'Status unavailable',
      message: 'Couldn’t check the worker. This doesn’t mean it has stopped.',
    };
  if (!snapshot.value)
    return {
      tone: 'loading',
      label: 'Checking worker',
      message: 'Checking the worker connection.',
    };
  if (isUnknown.value || snapshot.value.availability === 'stale')
    return {
      tone: 'warning',
      label: 'Worker not responding',
      message: 'No recent heartbeat. New runs may wait.',
    };
  const fault = snapshot.value.operational_faults[0];
  if (snapshot.value.availability === 'faulted' || fault)
    return {
      tone: 'error',
      label: 'Worker error',
      message:
        fault?.code === 'execution_slot_held'
          ? 'The execution slot needs recovery before new runs can start.'
          : (fault?.message ??
            'The worker reported a fault. New runs may not start.'),
    };
  if (snapshot.value.availability === 'unavailable')
    return {
      tone: 'warning',
      label: 'Worker offline',
      message:
        'The worker is unavailable. New runs will wait until it returns.',
    };
  return {
    tone: 'healthy',
    label: 'Worker online',
    message: '',
  };
});
const rows = computed(() => activityRows(snapshot.value, backtests.value));
const canRecheck = computed(() =>
  ['warning', 'error'].includes(health.value.tone),
);
const activityUncertain = computed(() => health.value.tone !== 'healthy');
const queuedCount = computed(
  () =>
    snapshot.value?.queued.reduce(
      (count, entry) => count + entry.outcome_counts.queued,
      0,
    ) ?? 0,
);
const hasWork = computed(
  () => !!snapshot.value?.active_run || !!snapshot.value?.queued.length,
);
const hasDetails = computed(
  () => health.value.tone !== 'healthy' || hasWork.value,
);
const pillLabel = computed(() => {
  if (health.value.tone !== 'healthy') return health.value.label;
  const activity = [
    snapshot.value?.active_run ? '1 running' : '',
    queuedCount.value ? `${queuedCount.value} queued` : '',
  ].filter(Boolean);
  return activity.join(' · ') || 'Worker online';
});
watch(hasDetails, (available) => {
  if (!available) expanded.value = false;
});
function inspect(id: string) {
  expanded.value = false;
  emit('inspect', id);
}
function close() {
  expanded.value = false;
  trigger.value?.focus();
}
function show() {
  visible.value = true;
}
function hide() {
  visible.value = false;
  expanded.value = false;
}
defineExpose({ refresh });
onMounted(show);
onActivated(show);
onDeactivated(hide);
onUnmounted(hide);
</script>

<template>
  <section
    v-if="visible"
    class="worker-health"
    aria-label="Backtest worker"
    data-testid="backtest-activity"
  >
    <BasePopover
      v-model:show="expanded"
      trigger="click"
      placement="top-end"
      :show-arrow="false"
      :width="300"
      :disabled="!hasDetails"
      :style="{ maxWidth: 'calc(100vw - 32px)' }"
    >
      <template #trigger>
        <button
          ref="trigger"
          class="health-pill"
          :class="health.tone"
          :aria-expanded="expanded"
          :aria-controls="panelId"
          :aria-label="`Backtests: ${pillLabel}`"
          :disabled="!hasDetails"
          data-testid="activity-toggle"
          @keydown.esc.stop="close"
        >
          <NSpin
            v-if="health.tone === 'loading'"
            :size="14"
            aria-hidden="true"
          />
          <span
            v-else
            class="health-dot"
            aria-hidden="true"
          />
          <span
            role="status"
            aria-live="polite"
            >{{ pillLabel }}</span
          >
        </button>
      </template>
      <div
        :id="panelId"
        class="health-detail"
        aria-label="Worker status details"
        @keydown.esc.stop="close"
      >
        <p v-if="health.message">{{ health.message }}</p>
        <div
          v-if="hasWork"
          class="active-work"
          :class="{ 'after-notice': !!health.message }"
        >
          <small
            v-if="activityUncertain"
            class="last-known"
            >Last known activity</small
          >
          <button
            v-for="row in rows"
            :key="row.id"
            class="work-row"
            :data-testid="`activity-backtest-${row.id}`"
            @click="inspect(row.id)"
          >
            <span class="work-name">{{ row.name }}</span>
            <span class="work-meta"
              >Run #{{ row.ordinal + 1 }} ·
              {{
                activityUncertain
                  ? `Was ${row.status.toLowerCase()}`
                  : row.status
              }}
              <span aria-hidden="true">→</span>
            </span>
            <span
              v-if="row.total"
              class="experiment-progress"
            >
              <span>{{ row.finished }} / {{ row.total }} finished</span>
              <progress
                :value="row.finished"
                :max="row.total"
                :aria-label="`${row.name} finished runs`"
              />
            </span>
          </button>
        </div>
        <NButton
          v-if="canRecheck"
          size="small"
          secondary
          @click="refresh()"
          :loading="isRefreshing"
          >Check again</NButton
        >
      </div>
    </BasePopover>
  </section>
</template>

<style scoped src="./backtestActivity.css"></style>
