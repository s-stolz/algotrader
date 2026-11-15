<template>
  <div class="broker-instrument-picker">
    <span v-if="connection">
      {{ connection.broker_name }} · {{ connection.environment }} ·
      {{ connection.account_id }}
    </span>
    <BaseSelect
      v-model:value="selectedId"
      aria-label="Broker instrument"
      placeholder="Select broker instrument"
      filterable
      :loading="loading"
      :disabled="loading"
      :options="options"
      @update:value="selectInstrument"
    />
    <div
      v-if="error"
      role="alert"
    >
      {{ error }}
      <n-button
        size="small"
        @click="loadSymbols"
        >Retry</n-button
      >
    </div>
    <span v-else-if="!loading && !options.length"
      >No enabled instruments are available.</span
    >
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { NButton } from 'naive-ui';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import {
  fetchBrokerConnection,
  fetchBrokerSymbols,
  fetchBrokerInstrument,
} from '@/api/brokerClient';
import type {
  BrokerConnection,
  BrokerInstrument,
  BrokerSymbol,
} from '@/types/brokerContracts';

const emit = defineEmits<{ verified: [instrument: BrokerInstrument | null] }>();
const connection = ref<BrokerConnection | null>(null);
const symbols = ref<BrokerSymbol[]>([]);
const selectedId = ref<number | null>(null);
const loading = ref(false);
const error = ref('');
let generation = 0;
const options = computed(() =>
  symbols.value.map((symbol) => ({
    label: symbol.symbolName,
    value: symbol.symbolId,
  })),
);

async function loadSymbols() {
  const request = ++generation;
  loading.value = true;
  selectedId.value = null;
  connection.value = null;
  symbols.value = [];
  emit('verified', null);
  error.value = '';
  try {
    const account = await fetchBrokerConnection();
    const instruments = await fetchBrokerSymbols(account.account_id);
    if (request !== generation) return;
    connection.value = account;
    symbols.value = instruments;
  } catch (cause) {
    if (request === generation)
      error.value =
        cause instanceof Error ? cause.message : 'Unable to load instruments';
  } finally {
    if (request === generation) loading.value = false;
  }
}

async function selectInstrument(id: number | null) {
  const request = ++generation;
  emit('verified', null);
  if (id === null || !connection.value) return;
  loading.value = true;
  error.value = '';
  try {
    const instrument = await fetchBrokerInstrument(
      id,
      connection.value.account_id,
    );
    if (request !== generation) return;
    if (instrument.broker_environment !== connection.value.environment) {
      throw new Error(
        'Broker environment changed. Reload the instrument list.',
      );
    }
    emit('verified', instrument);
  } catch (cause) {
    if (request === generation)
      error.value =
        cause instanceof Error ? cause.message : 'Unable to verify instrument';
  } finally {
    if (request === generation) loading.value = false;
  }
}

onMounted(loadSymbols);
onUnmounted(() => {
  generation += 1;
});
</script>

<style scoped>
.broker-instrument-picker {
  display: grid;
  gap: var(--design-space-sm);
}
[role='alert'] {
  color: var(--design-color-error);
}
</style>
