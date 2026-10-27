<template>
  <template v-if="selectedBatch">
    <div class="progress-panel">
      <div class="progress-heading">
        <div
          ><strong
            >{{ selectedBatch.settled_count }}
            <span>/ {{ selectedBatch.total_count }}</span></strong
          ><span class="progress-label">runs settled</span></div
        >
        <span class="progress-percent"
          >{{ progressPercent }}<small>%</small></span
        >
      </div>
      <div
        class="progress-track"
        role="progressbar"
        aria-label="Settled runs"
        :aria-valuenow="selectedBatch.settled_count"
        :aria-valuemin="0"
        :aria-valuemax="selectedBatch.total_count"
        :aria-valuetext="
          `${selectedBatch.settled_count} / ` +
          `${selectedBatch.total_count} settled; ` +
          `${selectedBatch.executed_count} executed`
        "
      >
        <span
          v-for="outcome in outcomes"
          :key="outcome.status"
          :class="outcome.status"
          :style="{
            width: `${(outcome.count / selectedBatch.total_count) * 100}%`,
          }"
        />
      </div>
      <div class="progress-caption">
        <span
          >{{ selectedBatch.executed_count }} executed
          <span class="muted">· Successes and failures</span></span
        >
        <span>{{
          detailError
            ? 'Updates interrupted'
            : isTerminal
              ? 'Final results'
              : 'Updates every 5 seconds'
        }}</span>
      </div>
      <dl class="outcome-grid">
        <div
          v-for="outcome in outcomes"
          :key="outcome.status"
          :class="outcome.status"
        >
          <dt><span class="legend-dot" />{{ outcome.label }}</dt
          ><dd>{{ outcome.count }}</dd>
        </div>
      </dl>
    </div>

    <div
      v-if="activityMessage"
      class="activity-panel"
      :class="{ 'is-live': !isTerminal && !detailError }"
    >
      <n-icon
        :component="activityIcon"
        size="20"
      />
      <div class="activity-copy">
        <p role="status">{{ activityMessage }}</p>
        <p
          v-if="activeMember"
          class="muted active-context"
        >
          {{ activeMember.request.symbols.join(', ') }} ·
          {{ activeMember.request.timeframe }}
          <span
            v-for="(value, name) in activeMember.request.strategy.parameters"
            :key="name"
          >
            · {{ parameterLabel(String(name)) }}: {{ JSON.stringify(value) }}
          </span>
        </p>
        <p
          v-if="selectedBatch.next_member_ordinal !== null"
          class="muted"
        >
          {{
            selectedBatch.status === 'paused' ||
            selectedBatch.status === 'pausing'
              ? 'Next on resume'
              : 'Up next'
          }}: run #{{ selectedBatch.next_member_ordinal + 1 }}
        </p>
      </div>
    </div>
  </template>
</template>
<script setup lang="ts">
import { NIcon } from 'naive-ui';
import type { BatchInspection } from './useBatchInspection';
const props = defineProps<{ inspection: BatchInspection }>();
const {
  selectedBatch,
  detailError,
  isTerminal,
  progressPercent,
  outcomes,
  activityMessage,
  activityIcon,
  activeMember,
  parameterLabel,
} = props.inspection;
</script>
<style scoped>
p {
  margin: 0;
}
.legend-dot {
  display: inline-block;
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.progress-panel {
  margin: 0 28px 16px;
  padding: 20px;
  border: 1px solid var(--surface-border);
  border-radius: 10px;
  background: var(--surface-inset);
}
.progress-heading {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 15px;
}
.progress-heading strong {
  font-size: 30px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.progress-heading strong span {
  font-size: 22px;
  color: #8fa3b5;
  font-weight: 400;
}
.progress-label {
  margin-left: 12px;
  color: #acbdca;
}
.progress-percent {
  color: #d9e8f3;
  font-size: 23px;
  font-variant-numeric: tabular-nums;
}
.progress-percent small {
  color: #8fa3b5;
  font-size: 13px;
  margin-left: 2px;
}
.progress-track {
  height: 8px;
  display: flex;
  overflow: hidden;
  border-radius: 6px;
  background: #303e4d;
}
.progress-track span {
  transition: width 0.35s ease;
}
.progress-track .succeeded {
  background: #68ceab;
}
.progress-track .failed {
  background: #ee9099;
}
.progress-track .cancelled {
  background: #8996a7;
}
.progress-track .running {
  background: repeating-linear-gradient(
    120deg,
    #578dba 0,
    #578dba 5px,
    #426d92 5px,
    #426d92 10px
  );
}
.progress-track .cancelling {
  background: #c8a169;
}
.progress-caption {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  font-size: 11px;
  color: #a9bccb;
}
.muted {
  color: #99adbd;
}
.outcome-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin: 22px 0 0;
}
.outcome-grid > div {
  border-left: 1px solid #304150;
  padding-left: 16px;
}
.outcome-grid > div:first-child {
  border-left: 0;
  padding-left: 0;
}
dt {
  color: #9fb2c2;
  font-size: 11px;
}
dd {
  margin: 6px 0 0;
}
.outcome-grid dt {
  display: flex;
  align-items: center;
  gap: 7px;
}
.outcome-grid dd {
  font-size: 22px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.succeeded .legend-dot,
.succeeded dd {
  color: #7cd8b7;
}
.failed .legend-dot,
.failed dd {
  color: #ee9ca5;
}
.cancelled .legend-dot {
  color: #a2afbf;
}
.running .legend-dot,
.running dd {
  color: #8dbfe9;
}
.cancelling .legend-dot {
  color: #edc791;
}
.queued .legend-dot {
  color: #71899d;
}
.activity-panel {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 20px 28px;
  padding: 4px 0;
  color: #a7bbcb;
}
.activity-panel.is-live > .n-icon {
  color: #91c4e9;
}
.activity-copy {
  flex: 1;
  min-width: 0;
}
.activity-copy > p:first-child {
  color: #d9e5ed;
  font-weight: 500;
}
.activity-copy .muted {
  font-size: 12px;
  margin-top: 5px;
  line-height: 1.6;
}
.active-context {
  overflow-wrap: anywhere;
  max-height: 90px;
  overflow: auto;
}
@media (prefers-reduced-motion: reduce) {
  .progress-track span {
    transition: none;
  }
}
@media (max-width: 600px) {
  .progress-panel {
    margin: 0 18px 16px;
    padding: 16px;
  }
  .outcome-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    row-gap: 20px;
  }
  .outcome-grid > div:nth-child(4) {
    border-left: 0;
    padding-left: 0;
  }
  .activity-panel {
    margin: 18px;
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .progress-label {
    display: block;
    margin: 2px 0 0;
    font-size: 12px;
  }
  .progress-caption .muted {
    display: none;
  }
}
</style>
