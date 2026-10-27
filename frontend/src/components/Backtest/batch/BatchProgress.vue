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
        class="activity-icon"
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
  border-radius: var(--design-radius-circle);
  background: currentColor;
}
.progress-panel {
  margin: 0 var(--design-space-xl) var(--design-space-lg);
  padding: var(--design-space-xl);
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
  background: var(--design-color-inset);
}
.progress-heading {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--design-space-md);
  margin-bottom: var(--design-space-lg);
}
.progress-heading strong {
  font-size: var(--design-text-metric);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.progress-heading strong span {
  font-size: var(--design-text-heading);
  color: var(--design-color-muted);
  font-weight: 400;
}
.progress-label {
  margin-left: var(--design-space-md);
  color: var(--design-color-muted);
}
.progress-percent {
  color: var(--design-color-body);
  font-size: var(--design-text-metric);
  font-variant-numeric: tabular-nums;
}
.progress-percent small {
  color: var(--design-color-muted);
  font-size: var(--design-text-body);
  margin-left: var(--design-space-xs);
}
.progress-track {
  height: 8px;
  display: flex;
  overflow: hidden;
  border-radius: var(--design-radius-panel);
  background: var(--design-color-disabled);
}
.progress-track span {
  transition: width 0.35s ease;
}
.progress-track .succeeded {
  background: var(--design-color-positive);
}
.progress-track .failed {
  background: var(--design-color-error);
}
.progress-track .cancelled {
  background: var(--design-color-muted);
}
.progress-track .running {
  background: repeating-linear-gradient(
    120deg,
    var(--design-color-info) 0,
    var(--design-color-info) 5px,
    var(--design-color-selected) 5px,
    var(--design-color-selected) 10px
  );
}
.progress-track .cancelling {
  background: var(--design-color-warning);
}
.progress-caption {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--design-space-sm);
  margin-top: var(--design-space-sm);
  font-size: var(--design-text-secondary);
  color: var(--design-color-muted);
}
.muted {
  color: var(--design-color-muted);
}
.outcome-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: var(--design-space-md);
  margin: var(--design-space-xl) 0 0;
}
.outcome-grid > div {
  border-left: 1px solid var(--design-color-border);
  padding-left: var(--design-space-lg);
}
.outcome-grid > div:first-child {
  border-left: 0;
  padding-left: 0;
}
dt {
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
dd {
  margin: var(--design-space-sm) 0 0;
}
.outcome-grid dt {
  display: flex;
  align-items: center;
  gap: var(--design-space-sm);
}
.outcome-grid dd {
  font-size: var(--design-text-metric);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.succeeded .legend-dot,
.succeeded dd {
  color: var(--design-color-positive);
}
.failed .legend-dot,
.failed dd {
  color: var(--design-color-error);
}
.cancelled .legend-dot {
  color: var(--design-color-muted);
}
.running .legend-dot,
.running dd {
  color: var(--design-color-info);
}
.cancelling .legend-dot {
  color: var(--design-color-warning);
}
.queued .legend-dot {
  color: var(--design-color-muted);
}
.activity-panel {
  display: flex;
  align-items: center;
  gap: var(--design-space-lg);
  margin: var(--design-space-xl) var(--design-space-xl);
  padding: var(--design-space-xs) 0;
  color: var(--design-color-muted);
}
.activity-panel.is-live > .activity-icon {
  color: var(--design-color-info);
}
.activity-copy {
  flex: 1;
  min-width: 0;
}
.activity-copy > p:first-child {
  color: var(--design-color-body);
  font-weight: 500;
}
.activity-copy .muted {
  font-size: var(--design-text-secondary);
  margin-top: var(--design-space-xs);
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
    margin: 0 var(--design-space-lg) var(--design-space-lg);
    padding: var(--design-space-lg);
  }
  .outcome-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    row-gap: var(--design-space-xl);
  }
  .outcome-grid > div:nth-child(4) {
    border-left: 0;
    padding-left: 0;
  }
  .activity-panel {
    margin: var(--design-space-lg);
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .progress-label {
    display: block;
    margin: var(--design-space-xs) 0 0;
    font-size: var(--design-text-secondary);
  }
  .progress-caption .muted {
    display: none;
  }
}
</style>
