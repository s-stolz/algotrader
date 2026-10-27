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
  color: #99adbd;
}
dt {
  color: #9fb2c2;
  font-size: 11px;
}
dd {
  margin: 6px 0 0;
}
.sweep-facts {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 20px;
  margin: 0;
  padding: 20px 28px;
  border-top: 1px solid #2d3b48;
}
.sweep-facts dd {
  font-size: 12px;
  line-height: 1.6;
}
.sweep-facts dd span {
  color: #9fb2c2;
}
.cancellation-note {
  margin: 0 28px 16px;
  color: #a9bccb;
  font-size: 12px;
}
.sweep-details {
  border-top: 1px solid #2d3b48;
}
.sweep-details > details {
  padding: 15px 28px;
}
.sweep-details > details + details {
  border-top: 1px solid #2d3b48;
}
summary {
  cursor: pointer;
  color: #c7d6e1;
  font-size: 12px;
}
summary::marker {
  color: #8aa3b7;
}
summary:focus-visible {
  outline: 2px solid #8dbfe9;
  outline-offset: 5px;
  border-radius: 2px;
}
summary > span {
  margin-left: 10px;
  color: #95aabb;
  font-size: 11px;
}
.settings-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
  margin: 20px 0;
}
.settings-grid dd {
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  line-height: 1.6;
}
.settings-grid small {
  margin-left: 5px;
  color: #bbcad5;
}
.technical-details {
  padding: 12px;
  background: var(--surface-inset);
  border-radius: 6px;
}
pre {
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 11px;
  color: #aabcca;
}
.event-timeline {
  list-style: none;
  padding: 0 0 0 15px;
  margin: 20px 0 0 4px;
  border-left: 1px solid #3b5163;
}
.event-timeline li {
  position: relative;
  padding: 0 0 20px 8px;
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
  background: #86a8bf;
  border-radius: 50%;
}
.event-heading {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px;
}
.event-heading strong {
  font-size: 12px;
  font-weight: 500;
}
.event-heading time {
  color: #9fb2c2;
  font-size: 11px;
}
.event-timeline p {
  margin-top: 5px;
  font-size: 12px;
  overflow-wrap: anywhere;
}
.event-identifiers {
  margin-top: 8px;
}
.event-identifiers summary {
  color: #97adbe;
  font-size: 11px;
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
    padding: 18px;
  }
  .settings-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
