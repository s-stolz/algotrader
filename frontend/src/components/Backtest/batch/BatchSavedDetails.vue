<template>
  <template v-if="selectedBatch">
    <dl class="sweep-facts">
      <div
        ><dt>Runs in sweep</dt
        ><dd
          >{{ selectedBatch.member_count }}
          <span>of {{ selectedBatch.raw_count }} combinations</span></dd
        ></div
      >
      <div
        ><dt>Excluded before starting</dt
        ><dd
          >{{ selectedBatch.excluded_count }}
          <span>invalid combinations</span></dd
        ></div
      >
      <div
        ><dt>Started · UTC</dt
        ><dd>{{ formatTimestamp(selectedBatch.started_at_ms) }}</dd></div
      >
      <div
        ><dt
          >{{
            selectedBatch.status === 'cancelled' ? 'Cancelled' : 'Finished'
          }}
          · UTC</dt
        ><dd>{{ formatTimestamp(selectedBatch.completed_at_ms) }}</dd></div
      >
    </dl>
    <p
      v-if="selectedBatch.cancel_requested_at_ms != null"
      class="cancellation-note"
    >
      Cancellation accepted:
      {{ formatTimestamp(selectedBatch.cancel_requested_at_ms) }} UTC.
    </p>

    <div class="sweep-details">
      <details>
        <summary>Sweep settings <span>Saved at submission</span></summary>
        <dl class="settings-grid">
          <div
            ><dt>Selected markets</dt
            ><dd>{{
              selections?.markets
                .map((market) => `${market.symbol} (${market.exchange})`)
                .join(', ')
            }}</dd></div
          >
          <div
            ><dt>Selected timeframes</dt
            ><dd>{{ selections?.timeframes.join(', ') }}</dd></div
          >
          <div
            ><dt>Allowed directions</dt
            ><dd>{{
              selections?.allowed_directions.map(directionLabel).join(', ')
            }}</dd></div
          >
          <div
            v-for="(axis, name) in selections?.parameters"
            :key="name"
          >
            <dt
              >{{ parameterLabel(String(name)) }}
              <small>{{ axis.mode }}</small></dt
            >
            <dd>{{
              axis.values.map((value) => JSON.stringify(value)).join(', ')
            }}</dd>
          </div>
        </dl>
        <details class="technical-details">
          <summary>Full saved definition and strategy metadata</summary>
          <p>Lifecycle revision {{ selectedBatch.lifecycle_revision }}</p>
          <pre>{{
            JSON.stringify(selectedBatch.accepted_definition, null, 2)
          }}</pre>
          <pre>{{
            JSON.stringify(selectedBatch.strategy_metadata, null, 2)
          }}</pre>
        </details>
      </details>
      <details v-if="events">
        <summary
          >Activity history <span>{{ events.length }} events</span></summary
        >
        <ol class="event-timeline">
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
              → {{ event.status }}
              <span class="muted">· revision {{ event.revision }}</span></p
            >
            <p
              v-if="event.reason"
              class="muted"
              >{{ eventLabel(event.reason) }}</p
            >
            <details
              v-if="event.trigger_run_id || event.command_id"
              class="event-identifiers"
            >
              <summary>Event identifiers</summary>
              <p v-if="event.trigger_run_id">run {{ event.trigger_run_id }}</p>
              <p v-if="event.command_id">command {{ event.command_id }}</p>
            </details>
          </li>
        </ol>
      </details>
    </div>
  </template>
</template>
<script setup lang="ts">
import type { BatchInspection } from './useBatchInspection';
const props = defineProps<{ inspection: BatchInspection }>();
const {
  selectedBatch,
  selections,
  events,
  formatTimestamp,
  directionLabel,
  parameterLabel,
  eventLabel,
} = props.inspection;
</script>
<style scoped>
p {
  margin: 0;
}
.muted {
  color: var(--design-color-muted);
}
dt {
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
dd {
  margin: var(--design-space-sm) 0 0;
}
.sweep-facts {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--design-space-xl);
  margin: 0;
  padding: var(--design-space-xl) var(--design-space-xl);
  border-top: 1px solid var(--design-color-border);
}
.sweep-facts dd {
  font-size: var(--design-text-secondary);
  line-height: 1.6;
}
.sweep-facts dd span {
  color: var(--design-color-muted);
}
.cancellation-note {
  margin: 0 var(--design-space-xl) var(--design-space-lg);
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
.sweep-details {
  border-top: 1px solid var(--design-color-border);
}
.sweep-details > details {
  padding: var(--design-space-lg) var(--design-space-xl);
}
.sweep-details > details + details {
  border-top: 1px solid var(--design-color-border);
}
summary {
  cursor: pointer;
  color: var(--design-color-body);
  font-size: var(--design-text-secondary);
}
summary::marker {
  color: var(--design-color-muted);
}
summary:focus-visible {
  outline: 2px solid var(--design-color-interactive);
  outline-offset: 5px;
  border-radius: var(--design-radius-panel);
}
summary > span {
  margin-left: var(--design-space-sm);
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
.settings-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--design-space-xl);
  margin: var(--design-space-xl) 0;
}
.settings-grid dd {
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  line-height: 1.6;
}
.settings-grid small {
  margin-left: var(--design-space-xs);
  color: var(--design-color-muted);
}
.technical-details {
  padding: var(--design-space-md);
  background: var(--design-color-inset);
  border-radius: var(--design-radius-panel);
}
pre {
  font-family: var(--design-font-mono);
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: var(--design-text-id);
  color: var(--design-color-muted);
}
.event-timeline {
  list-style: none;
  padding: 0 0 0 var(--design-space-lg);
  margin: var(--design-space-xl) 0 0 var(--design-space-xs);
  border-left: 1px solid var(--design-color-border);
}
.event-timeline li {
  position: relative;
  padding: 0 0 var(--design-space-xl) var(--design-space-sm);
}
.event-timeline li:last-child {
  padding-bottom: 0;
}
.event-timeline li::before {
  content: '';
  position: absolute;
  left: -20px;
  top: 5px;
  width: 7px;
  height: 7px;
  background: var(--design-color-muted);
  border-radius: var(--design-radius-circle);
}
.event-heading {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--design-space-sm);
}
.event-heading strong {
  font-size: var(--design-text-secondary);
  font-weight: 500;
}
.event-heading time {
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
.event-timeline p {
  margin-top: var(--design-space-xs);
  font-size: var(--design-text-secondary);
  overflow-wrap: anywhere;
}
.event-identifiers p {
  font-family: var(--design-font-mono);
  font-size: var(--design-text-id);
}
.event-identifiers {
  margin-top: var(--design-space-sm);
}
.event-identifiers summary {
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
}
@media (max-width: 900px) {
  .sweep-facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .settings-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .sweep-facts,
  .sweep-details > details {
    padding: var(--design-space-lg);
  }
  .settings-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
