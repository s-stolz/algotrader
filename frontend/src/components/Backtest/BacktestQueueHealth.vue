<template>
  <section
    class="queue-health"
    aria-label="Backtest queue"
    data-testid="workspace-queue"
  >
    <div class="queue-summary">
      <n-icon
        size="17"
        class="queue-icon"
        ><server-outline
      /></n-icon>
      <h2>Queue and worker</h2>
      <n-tag
        :type="healthType"
        size="small"
        round
        :bordered="false"
        class="health-tag"
      >
        {{
          isUnknown
            ? 'Status unknown'
            : (snapshot?.availability ?? 'Connecting')
        }}
      </n-tag>
      <span
        v-if="snapshot"
        class="queue-summary-count"
      >
        {{ isUnknown ? 'Last known: ' : ''
        }}{{ snapshot.active_run ? '1 active run' : 'Idle' }} ·
        {{ snapshot.queued.length }} waiting
      </span>
    </div>
    <n-skeleton
      v-if="!snapshot && !readError"
      text
      :repeat="2"
      class="queue-loading"
      aria-label="Loading queue health"
    />
    <n-alert
      v-if="isUnknown"
      type="warning"
      class="queue-alert"
      data-testid="workspace-queue-unknown"
    >
      Queue and worker status unknown{{
        readError ? `: ${readError}` : '; latest snapshot is old'
      }}.
    </n-alert>
    <details
      v-if="snapshot"
      class="queue-details"
    >
      <summary>Activity details</summary>
      <div class="worker-metrics">
        <div
          class="worker-state"
          data-testid="workspace-worker-status"
        >
          <span class="metric-label">Worker status</span>
          <n-tag
            :type="healthType"
            :bordered="false"
          >
            {{
              isUnknown ? 'Status unknown' : `Worker ${snapshot.availability}`
            }}
          </n-tag>
        </div>
        <n-statistic
          :label="isUnknown ? 'Last known heartbeat' : 'Last heartbeat'"
          :value="
            snapshot.last_heartbeat_ms === null
              ? '—'
              : elapsed(snapshot.last_heartbeat_ms)
          "
        >
          <template
            v-if="snapshot.last_heartbeat_ms !== null"
            #suffix
            ><span class="metric-suffix">ago</span></template
          >
          <template
            v-else
            #suffix
            ><span class="metric-suffix"
              >No worker heartbeat recorded</span
            ></template
          >
        </n-statistic>
        <n-statistic
          :label="isUnknown ? 'Last known snapshot' : 'Snapshot age'"
          :value="elapsed(snapshot.snapshot_at_ms)"
        >
          <template #suffix><span class="metric-suffix">ago</span></template>
        </n-statistic>
      </div>
      <div
        v-if="snapshot.operational_faults.length"
        class="faults"
        aria-label="Worker faults"
      >
        <n-alert
          v-for="fault in snapshot.operational_faults"
          :key="fault.code"
          type="error"
          :title="fault.message"
        >
          <code>{{ fault.code }}</code>
        </n-alert>
      </div>
      <div class="activity-grid">
        <section
          class="activity-card"
          aria-label="Active execution"
        >
          <header class="activity-heading">
            <n-icon size="16"><pulse-outline /></n-icon>
            <h3>{{ isUnknown ? 'Last known active run' : 'Active run' }}</h3>
            <n-tag
              v-if="snapshot.active_run"
              size="small"
              :bordered="false"
              :type="isUnknown ? 'default' : 'info'"
            >
              {{ isUnknown ? 'Last known' : 'In progress' }}
            </n-tag>
          </header>
          <div
            v-if="snapshot.active_run"
            class="active-run"
            data-testid="workspace-queue-active"
          >
            <span class="metric-label">{{
              isUnknown ? 'Last known active run' : 'Run ID'
            }}</span>
            <code class="run-identity">{{ snapshot.active_run.run_id }}</code>
            <span class="run-duration"
              ><n-icon><time-outline /></n-icon>
              {{ isUnknown ? 'Started' : 'Active for' }}
              {{ elapsed(snapshot.active_run.started_at_ms)
              }}{{ isUnknown ? ' ago' : '' }}
            </span>
            <div
              v-if="snapshot.active_run.batch_id"
              class="active-batch"
            >
              <n-tag
                size="small"
                :bordered="false"
                >Member #{{
                  (snapshot.active_run.member_ordinal ?? 0) + 1
                }}</n-tag
              >
              <span class="metric-label"
                >Batch <code>{{ snapshot.active_run.batch_id }}</code></span
              >
            </div>
          </div>
          <n-empty
            v-else
            size="small"
            class="activity-empty"
            data-testid="workspace-queue-no-active"
            :description="
              isUnknown ? 'Last known active run: none' : 'No active run'
            "
          >
            <template #icon
              ><n-icon><pause-circle-outline /></n-icon
            ></template>
          </n-empty>
        </section>
        <section
          class="activity-card"
          aria-label="Waiting queue"
        >
          <header class="activity-heading">
            <n-icon size="16"><list-outline /></n-icon>
            <h3>{{ isUnknown ? 'Last known queue' : 'Waiting queue' }}</h3>
            <n-tag
              size="small"
              round
              :bordered="false"
              >{{ snapshot.queued.length }}</n-tag
            >
          </header>
          <n-empty
            v-if="snapshot.queued.length === 0"
            size="small"
            class="activity-empty"
            data-testid="workspace-queue-empty"
            :description="
              isUnknown
                ? 'Last known queue had no waiting work'
                : 'No waiting work'
            "
          >
            <template #icon
              ><n-icon><checkmark-circle-outline /></n-icon
            ></template>
          </n-empty>
          <ol
            v-else
            class="waiting-list"
            aria-label="Waiting backtests"
          >
            <li
              v-for="entry in snapshot.queued"
              :key="
                entry.entry_type === 'batch'
                  ? `batch:${entry.batch_id}`
                  : `run:${entry.run_id}`
              "
              :data-testid="
                entry.entry_type === 'batch'
                  ? `workspace-queue-batch-${entry.batch_id}`
                  : `workspace-queue-run-${entry.run_id}`
              "
            >
              <div class="waiting-heading">
                <n-tag
                  size="small"
                  :bordered="false"
                  type="info"
                  >Est. #{{ entry.estimated_position }}</n-tag
                >
                <span>{{
                  entry.entry_type === 'batch' ? 'Batch' : 'Run'
                }}</span>
                <span class="waiting-time"
                  >Waiting {{ elapsed(entry.submitted_at_ms) }}</span
                >
              </div>
              <code class="run-identity">{{
                entry.entry_type === 'batch' ? entry.batch_id : entry.run_id
              }}</code>
              <div
                v-if="entry.entry_type === 'batch'"
                class="batch-outcomes"
              >
                <span class="metric-label"
                  >Next member #{{ (entry.next_member_ordinal ?? 0) + 1 }}</span
                >
                <n-tag
                  size="small"
                  :bordered="false"
                  type="success"
                  >{{ entry.outcome_counts?.succeeded ?? 0 }} succeeded</n-tag
                >
                <n-tag
                  size="small"
                  :bordered="false"
                  :type="entry.outcome_counts?.failed ? 'error' : 'default'"
                  >{{ entry.outcome_counts?.failed ?? 0 }} failed</n-tag
                >
                <n-tag
                  size="small"
                  :bordered="false"
                  >{{ entry.outcome_counts?.cancelled ?? 0 }} cancelled</n-tag
                >
              </div>
            </li>
          </ol>
        </section>
      </div>
      <p class="telemetry-note"
        ><n-icon size="14"><information-circle-outline /></n-icon>
        Queue positions are estimates and may change; no start time or ETA is
        promised.
      </p>
    </details>
  </section>
</template>

<script setup lang="ts">
import { NAlert, NEmpty, NIcon, NSkeleton, NStatistic, NTag } from 'naive-ui';
import {
  CheckmarkCircleOutline,
  InformationCircleOutline,
  ListOutline,
  PauseCircleOutline,
  PulseOutline,
  ServerOutline,
  TimeOutline,
} from '@vicons/ionicons5';
import { useBacktestQueueHealth } from './useBacktestQueueHealth';
const { snapshot, readError, isUnknown, healthType, elapsed, refresh } =
  useBacktestQueueHealth();
defineExpose({ refresh });
</script>

<style scoped src="./backtestQueueHealth.css"></style>
