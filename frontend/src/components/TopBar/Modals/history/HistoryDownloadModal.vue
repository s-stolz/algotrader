<template>
  <BaseModal
    ref="modal"
    modal-id="historyDownload"
    :title="`Download history · ${market.symbol}`"
  >
    <div class="history-download">
      <BaseAsyncState
        v-if="loading"
        kind="loading"
        label="Loading stored history"
      />
      <template v-else>
        <dl
          v-if="coverage?.candle_count"
          class="coverage"
        >
          <dt>Oldest candle</dt
          ><dd>{{ timestamp(coverage.oldest_timestamp_ms) }}</dd>
          <dt>Latest candle</dt
          ><dd>{{ timestamp(coverage.latest_timestamp_ms) }}</dd>
          <dt>Stored M1 candles</dt
          ><dd>{{ coverage.candle_count.toLocaleString() }}</dd>
        </dl>
        <p v-else>No candles stored.</p>
        <p class="hint"
          >Extend history before the oldest stored candle. Stored dates do not
          guarantee gap-free data.</p
        >
        <template v-if="!active">
          <label>Download by</label>
          <BaseSelect
            v-model:value="mode"
            aria-label="Download by"
            :options="requestOptions"
          />
          <template v-if="mode === 'date'">
            <label for="history-start-date">Back to date (UTC)</label>
            <n-input
              id="history-start-date"
              v-model:value="startDate"
              type="text"
              placeholder="YYYY-MM-DD"
              aria-label="Back to date (UTC)"
            />
          </template>
          <template v-else>
            <label>Additional one-minute candles</label>
            <n-input-number
              v-model:value="candleCount"
              :min="1"
              :max="1000000"
              :precision="0"
              aria-label="Additional one-minute candles"
            />
          </template>
        </template>
        <section
          v-if="current"
          class="download-status"
          aria-label="Download status"
        >
          <strong>{{ statusLabels[current.status] }}</strong>
          <span
            >{{ current.inserted_count.toLocaleString() }} one-minute candles
            downloaded</span
          >
          <span v-if="current.candle_count"
            >Requested {{ current.candle_count.toLocaleString() }} candles</span
          >
          <span v-if="current.status === 'downloading'"
            >Checked back to {{ timestamp(current.cursor_ms) }}</span
          >
          <span
            v-if="current.failure_reason"
            role="alert"
            >{{ current.failure_reason }}</span
          >
          <span v-if="current.availability_reason">{{
            current.availability_reason
          }}</span>
          <span v-if="active && !connected">Live progress is unavailable.</span>
          <n-button
            v-if="active"
            :loading="submitting"
            :disabled="current.cancel_requested"
            @click="change('cancel')"
            >{{
              current.cancel_requested ? 'Cancelling…' : 'Cancel download'
            }}</n-button
          >
          <n-button
            v-else-if="
              current.status === 'failed' || current.status === 'cancelled'
            "
            :loading="submitting"
            @click="change('retry')"
            >Retry download</n-button
          >
        </section>
      </template>
      <div
        v-if="error"
        role="alert"
        >{{ error }}</div
      >
      <n-button
        v-if="error || (!connected && active)"
        size="small"
        @click="refresh"
        >Refresh status</n-button
      >
    </div>
    <template #footer>
      <n-button @click="modal?.close()">{{
        offer ? 'Skip' : 'Close'
      }}</n-button>
      <n-button
        v-if="!active"
        :loading="submitting"
        :disabled="loading || !coverage"
        @click="submit"
        >Download</n-button
      >
    </template>
  </BaseModal>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { NButton, NInput, NInputNumber } from 'naive-ui';
import BaseModal from '@/components/Common/BaseModal.vue';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';
import type { Market } from '@/types/contracts';
import { useHistoryDownloads } from './useHistoryDownloads';

const props = defineProps<{ market: Market; offer?: boolean }>();
const modal = ref<{ close: () => void } | null>(null);
const {
  coverage,
  current,
  active,
  loading,
  submitting,
  error,
  connected,
  mode,
  startDate,
  candleCount,
  submit,
  change,
  refresh,
} = useHistoryDownloads(props.market.symbol_id);
const requestOptions = [
  { label: 'Start date', value: 'date' },
  { label: 'Candle count', value: 'count' },
];
const statusLabels = {
  queued: 'Queued',
  downloading: 'Downloading',
  completed: 'Completed',
  failed: 'Download failed',
  cancelled: 'Cancelled',
};
function timestamp(value: number | null): string {
  return value === null
    ? 'None'
    : `${new Date(value).toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}
</script>

<style scoped>
.history-download {
  display: grid;
  gap: var(--design-space-sm);
  padding: var(--design-space-lg);
}
.coverage {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--design-space-xs) var(--design-space-md);
  margin: 0;
}
.coverage dd {
  margin: 0;
}
.hint {
  color: var(--design-color-muted);
}
.download-status {
  display: grid;
  gap: var(--design-space-sm);
}
[role='alert'] {
  color: var(--design-color-error);
}
</style>
