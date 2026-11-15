<template>
  <div
    v-if="selectedBacktest"
    class="selections-details"
  >
    <details
      :key="`${selectedBacktest.backtest_id}-configuration`"
      class="configuration-section"
    >
      <summary>Configuration</summary>
      <dl class="settings-grid">
        <div v-if="period"
          ><dt>Backtest period · UTC</dt><dd>{{ period }}</dd></div
        >
        <div
          ><dt>Execution duration</dt
          ><dd data-testid="backtest-duration">{{ elapsed }}</dd></div
        >
        <div
          ><dt>Markets</dt
          ><dd class="values"
            ><span
              v-for="market in selections?.markets"
              :key="market.symbol_id"
              class="value-pill"
              >{{ market.symbol }} · {{ market.exchange }}</span
            ></dd
          ></div
        >
        <div
          ><dt>Timeframes</dt
          ><dd class="values"
            ><span
              v-for="timeframe in selections?.timeframes"
              :key="timeframe"
              class="value-pill"
              >{{ timeframe }}</span
            ></dd
          ></div
        >
        <div
          ><dt>Allowed directions</dt
          ><dd class="values"
            ><span
              v-for="direction in selections?.allowed_directions"
              :key="direction"
              class="value-pill"
              >{{ directionLabel(direction) }}</span
            ></dd
          ></div
        >
        <div
          v-for="(axis, name) in selections?.parameters"
          :key="name"
        >
          <dt>{{ parameterLabel(String(name)) }}</dt>
          <dd
            v-if="axis.range"
            class="range-value"
            ><strong>{{ axis.range.start }} → {{ axis.range.stop }}</strong
            ><span
              >step {{ axis.range.step }} ·
              {{ axis.values.length }} values</span
            ></dd
          >
          <dd
            v-else
            class="values"
            ><span
              v-for="(value, index) in axis.values"
              :key="index"
              class="value-pill"
              >{{ displayValue(value) }}</span
            ></dd
          >
        </div>
        <div v-if="selections?.daily_schedules"
          ><dt>Schedules · UTC (start / last entry / exit)</dt
          ><dd
            v-for="(schedule, index) in selections.daily_schedules"
            :key="index"
            >{{ scheduleLabel(schedule) }}</dd
          ></div
        >
        <div
          ><dt>Runs</dt
          ><dd
            >{{ selectedBacktest.member_count }} of
            {{ selectedBacktest.raw_count }} combinations</dd
          ></div
        >
        <div v-if="selectedBacktest.excluded_count"
          ><dt>Excluded combinations</dt
          ><dd>{{ selectedBacktest.excluded_count }}</dd></div
        >
        <div
          ><dt>Execution outcome</dt
          ><dd class="values"
            ><span
              v-for="outcome in nonemptyOutcomes"
              :key="outcome.status"
              :data-testid="`backtest-outcome-${outcome.status}`"
              class="value-pill"
              >{{ outcome.label }} {{ outcome.count }}</span
            ></dd
          ></div
        >
        <div
          ><dt>Started · UTC</dt
          ><dd>{{ formatTimestamp(selectedBacktest.started_at_ms) }}</dd></div
        >
        <div v-if="selectedBacktest.completed_at_ms !== null"
          ><dt>Finished · UTC</dt
          ><dd>{{ formatTimestamp(selectedBacktest.completed_at_ms) }}</dd></div
        >
      </dl>
      <p
        v-if="selectedBacktest.cancel_requested_at_ms != null"
        class="cancellation-note"
        >Cancellation accepted:
        {{ formatTimestamp(selectedBacktest.cancel_requested_at_ms) }} UTC.</p
      >
    </details>
    <details
      v-if="events"
      :key="`${selectedBacktest.backtest_id}-activity`"
      class="activity-section"
    >
      <summary
        >Activity <span class="event-count">{{ events.length }}</span></summary
      >
      <ol
        v-if="events.length"
        class="event-timeline"
      >
        <li
          v-for="event in events"
          :key="event.revision"
        >
          <div class="event-heading"
            ><strong>{{ eventLabel(event.event_type) }}</strong
            ><time>{{ formatTimestamp(event.occurred_at_ms) }} UTC</time></div
          >
          <p
            >{{
              event.prior_status ??
              (event.revision === 0 ? 'initial' : 'unknown')
            }}
            → {{ event.status }}</p
          >
          <p
            v-if="event.reason"
            class="muted"
            >{{ eventLabel(event.reason) }}</p
          >
          <div
            v-if="event.trigger_run_id || event.command_id"
            class="event-identifiers"
          >
            <code
              v-if="event.trigger_run_id"
              :title="event.trigger_run_id"
              :aria-label="`Run ${event.trigger_run_id}`"
              >Run {{ event.trigger_run_id.slice(0, 8) }}</code
            >
            <code
              v-if="event.command_id"
              :title="event.command_id"
              :aria-label="`Command ${event.command_id}`"
              >Cmd {{ event.command_id.slice(0, 8) }}</code
            >
          </div>
        </li>
      </ol>
      <p
        v-else
        class="muted"
        >No activity recorded.</p
      >
    </details>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue';
import type { BacktestInspection } from './useBacktestInspection';
import { scheduleLabel } from '@/types/backtest/schedule';
const props = defineProps<{ inspection: BacktestInspection }>();
const {
  selectedBacktest,
  selections,
  events,
  elapsed,
  outcomes,
  formatTimestamp,
  directionLabel,
  parameterLabel,
  eventLabel,
} = props.inspection;
const nonemptyOutcomes = computed(() =>
  outcomes.value.filter((outcome) => outcome.count > 0),
);
const period = computed(() => {
  const request = selectedBacktest.value?.accepted_definition.shared_request;
  if (
    typeof request?.start_ms !== 'number' ||
    typeof request?.end_ms !== 'number'
  )
    return null;
  const start = new Date(request.start_ms).toISOString().slice(0, 10);
  const end = new Date(request.end_ms).toISOString().slice(0, 10);
  return `${start} – ${end}`;
});
function displayValue(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value);
}
</script>
<style scoped>
.selections-details {
  padding: 20px 24px;
  border-top: 1px solid var(--design-color-border);
}
summary {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  list-style: none;
  font-weight: 500;
  padding: 4px 0;
}
summary::-webkit-details-marker {
  display: none;
}
summary::before {
  content: '+';
  width: 18px;
  flex-shrink: 0;
  color: var(--design-color-muted);
  font-size: 20px;
  line-height: 1;
  text-align: center;
}
details[open] > summary::before {
  content: '−';
}
summary:focus-visible {
  outline: 2px solid var(--design-color-interactive);
  outline-offset: 5px;
  border-radius: var(--design-radius-panel);
}
.settings-grid {
  margin: 16px 0 0;
}
.settings-grid > div {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  align-items: start;
  gap: 16px;
  padding: 9px 0;
  border-bottom: 1px solid var(--design-color-border);
}
dt {
  margin: 0;
  padding-top: 2px;
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
  line-height: 22px;
  overflow-wrap: anywhere;
}
dd {
  grid-column: 2;
  min-width: 0;
  margin: 0;
  padding: 2px 8px;
  line-height: 22px;
  overflow-wrap: anywhere;
}
.values {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 0;
}
.value-pill {
  padding: 2px 8px;
  border-radius: 12px;
  background: var(--design-color-inset);
  font-variant-numeric: tabular-nums;
}
.range-value {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 12px;
}
.range-value strong {
  font-weight: 500;
}
.range-value span,
.event-count,
.muted,
time {
  color: var(--design-color-muted);
}
.range-value span,
time,
.event-count {
  font-size: var(--design-text-secondary);
}
p {
  margin: 6px 0;
  font-size: var(--design-text-secondary);
  overflow-wrap: anywhere;
}
.cancellation-note {
  margin-top: 16px;
  color: var(--design-color-muted);
}
.activity-section {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--design-color-border);
}
.event-timeline {
  list-style: none;
  display: flex;
  width: 100%;
  box-sizing: border-box;
  gap: 0;
  margin: 16px 0 0;
  padding: 8px 0 0;
  overflow-x: auto;
}
.event-timeline li {
  position: relative;
  flex: 1 0 190px;
  min-width: 190px;
  box-sizing: border-box;
  padding: 20px 10px 8px;
  text-align: center;
}
.event-timeline li::before {
  content: '';
  position: absolute;
  z-index: 1;
  top: 1px;
  left: 50%;
  transform: translateX(-50%);
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--design-color-interactive);
}
.event-timeline li::after {
  content: '';
  position: absolute;
  top: 4px;
  left: 0;
  width: 100%;
  height: 1px;
  background: var(--design-color-border);
}
.event-timeline li:first-child::after {
  left: 50%;
  width: 50%;
}
.event-timeline li:last-child::after {
  width: 50%;
}
.event-timeline li:only-child::after {
  display: none;
}
.event-timeline li:last-child::before {
  box-shadow: 0 0 0 4px var(--design-color-inset);
}
.event-heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.event-heading strong {
  font-size: var(--design-text-secondary);
  font-weight: 500;
}
.event-identifiers {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
  margin-top: 10px;
}
code {
  display: inline-block;
  max-width: 100%;
  overflow-wrap: anywhere;
  border: 1px solid var(--design-color-border);
  border-radius: 12px;
  padding: 3px 8px;
  font-family: var(--design-font-mono);
  font-size: var(--design-text-id);
  color: var(--design-color-muted);
}
@media (max-width: 750px) {
  .settings-grid > div {
    grid-template-columns: 120px minmax(0, 1fr);
  }
}
@media (max-width: 600px) {
  .selections-details {
    padding: var(--design-space-lg);
  }
}
</style>
