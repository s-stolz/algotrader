<template>
  <n-drawer :show="show" width="min(540px, 100vw)" @update:show="emit('update:show', $event)">
    <n-drawer-content title="Create standalone Backtest" closable>
      <p v-if="catalogError" role="alert">Strategy catalog unavailable. {{ catalogError }}</p>
      <n-button v-if="catalogError" @click="loadCatalog">Retry catalog</n-button>
      <template v-if="draft && catalog.length">
        <div class="creation-fields">
          <label>Strategy
            <n-select
              :value="draft.strategy.strategy_id"
              :options="strategyOptions"
              data-testid="creation-strategy"
              @update:value="selectStrategy"
            />
          </label>
          <p
            v-if="selectedStrategy && selectedStrategy.strategy_version !== draft.strategy.strategy_version"
            role="alert"
          >
            Strategy version changed. Review the current schema before submitting.
            <n-button size="small" @click="useCurrentVersion">Use current version</n-button>
          </p>
          <p v-else-if="selectedStrategy">Version {{ selectedStrategy.strategy_version }}</p>
          <template v-for="parameter in selectedStrategy?.parameters ?? []" :key="parameter.name">
            <label :for="`parameter-${parameter.name}`">{{ parameter.display_name || parameter.name }}
              <span v-if="parameter.required"> *</span>
            </label>
            <n-select
              v-if="parameter.choices || parameter.type === 'bool'"
              :id="`parameter-${parameter.name}`"
              :value="selectValue(parameter)"
              :options="parameterOptions(parameter)"
              :data-testid="`creation-param-${parameter.name}`"
              @update:value="setChoice(parameter, $event)"
            />
            <n-input-number
              v-else-if="parameter.type === 'int' || parameter.type === 'float'"
              :id="`parameter-${parameter.name}`"
              :value="numberValue(parameter.name)"
              :min="parameter.minimum"
              :max="parameter.maximum"
              :precision="parameter.type === 'int' ? 0 : undefined"
              :data-testid="`creation-param-${parameter.name}`"
              @update:value="setParameter(parameter.name, $event)"
            />
            <n-input
              v-else
              :id="`parameter-${parameter.name}`"
              :value="stringValue(parameter.name)"
              :data-testid="`creation-param-${parameter.name}`"
              @update:value="setParameter(parameter.name, $event)"
            />
            <n-button
              v-if="parameter.nullable && !parameter.choices && parameter.type !== 'bool'"
              size="tiny"
              @click="setParameter(parameter.name, null)"
            >Set null</n-button>
            <small v-if="parameter.nullable && draft.strategy.parameters[parameter.name] === null">
              Null selected
            </small>
            <small v-if="parameter.minimum !== undefined || parameter.maximum !== undefined">
              <template v-if="parameter.minimum !== undefined">
                {{ parameter.exclusive_minimum ? '>' : '≥' }} {{ parameter.minimum }}
              </template>
              <template v-if="parameter.maximum !== undefined">
                {{ parameter.exclusive_maximum ? '<' : '≤' }} {{ parameter.maximum }}
              </template>
            </small>
            <small v-if="parameter.description">{{ parameter.description }}</small>
            <small v-if="fieldErrors[parameter.name]" role="alert">{{ fieldErrors[parameter.name] }}</small>
          </template>
          <label>Market
            <n-select
              :value="marketValue"
              :options="marketOptions"
              data-testid="creation-market"
              @update:value="selectMarket"
            />
          </label>
          <small v-if="!marketOptions.length" role="alert">Market options unavailable.</small>
          <small v-if="fieldErrors.market" role="alert">{{ fieldErrors.market }}</small>
          <label>Timeframe
            <n-select
              v-model:value="draft.timeframe"
              :options="timeframeOptions"
              data-testid="creation-timeframe"
            />
          </label>
          <label>Start date (UTC)
            <input
              type="date"
              :value="dateValue(draft.start_ms)"
              data-testid="creation-start"
              @input="setDate('start_ms', $event)"
            />
          </label>
          <label>End date (UTC)
            <input
              type="date"
              :value="dateValue(draft.end_ms)"
              data-testid="creation-end"
              @input="setDate('end_ms', $event)"
            />
          </label>
          <small v-if="fieldErrors.dates" role="alert">{{ fieldErrors.dates }}</small>
          <label>Initial capital
            <n-input-number
              v-model:value="draft.initial_capital"
              :min="0.01"
              data-testid="creation-capital"
            />
          </label>
          <small v-if="fieldErrors.capital" role="alert">{{ fieldErrors.capital }}</small>
          <details>
            <summary>Execution settings</summary>
            <label>Allowed Directions
              <n-select
                v-model:value="draft.execution.allowed_directions"
                :options="directionOptions"
                data-testid="creation-directions"
              />
            </label>
            <label>Engine
              <n-select v-model:value="draft.engine" :options="engineOptions" />
            </label>
            <label>Commission (bps)
              <n-input-number v-model:value="draft.execution.commission_bps" :min="0" />
            </label>
            <label>Slippage (bps)
              <n-input-number v-model:value="draft.execution.slippage_bps" :min="0" />
            </label>
            <label>Gap policy
              <n-select v-model:value="draft.execution.gap_policy" :options="gapOptions" />
            </label>
            <label>Intrabar exit policy
              <n-select v-model:value="draft.execution.intrabar_exit_policy" :options="exitOptions" />
            </label>
          </details>
        </div>
        <p v-if="submitError" role="alert">{{ submitError }}</p>
      </template>
      <template #footer>
        <n-button
          v-if="draft && catalog.length"
          :disabled="submitting || !marketOptions.length || !!catalogError"
          :loading="submitting"
          data-testid="creation-submit"
          @click="submit"
        >Create Backtest</n-button>
      </template>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from 'vue';
import { NButton, NDrawer, NDrawerContent, NInput, NInputNumber, NSelect } from 'naive-ui';
import type { SelectOption } from 'naive-ui';
import { BacktestSubmissionError, fetchStrategyCatalog, submitBacktestRun } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { BacktestRequestPayload, StrategyCatalogEntry, StrategyParameterSchema } from '@/types/backtesterContracts';
import { TIMEFRAME_CODES } from '@/types/contracts';

type DraftRequest = Omit<BacktestRequestPayload, 'strategy' | 'run_metadata'> & {
  strategy: { strategy_id: string; strategy_version?: number; parameters: Record<string, null | boolean | number | string> };
  run_metadata: null;
};

defineProps<{ show: boolean }>();
const emit = defineEmits<{ 'update:show': [show: boolean]; submitted: [runId: string] }>();
const store = useBacktestWorkspaceStore();
const markets = useMarketsStore();
const draft = ref<DraftRequest>((store.creationDraft as DraftRequest | null) ?? initialDraft());
const catalog = shallowRef<StrategyCatalogEntry[]>([]);
const catalogError = ref<string | null>(null);
const submitError = ref<string | null>(null);
const fieldErrors = ref<Record<string, string>>({});
const submitting = ref(false);
const selectedStrategy = computed(() => catalog.value.find(
  (entry) => entry.strategy_id === draft.value.strategy.strategy_id,
));
const strategyOptions = computed<SelectOption[]>(() => catalog.value.map((entry) => ({
  label: `${entry.display_name} · v${entry.strategy_version}`, value: entry.strategy_id,
})));
const marketOptions = computed<SelectOption[]>(() => markets.all.map((market) => ({
  label: `${market.symbol} · ${market.exchange}`, value: market.symbol_id,
})));
const marketValue = computed(() => markets.all.find((market) =>
  market.symbol === draft.value.symbols[0] && market.exchange === draft.value.exchange)?.symbol_id);
const timeframeOptions: SelectOption[] = TIMEFRAME_CODES.map((code) => ({
  label: code, value: code,
}));
const directionOptions: SelectOption[] = [
  { label: 'Long and short', value: 'long_and_short' },
  { label: 'Long only', value: 'long_only' },
  { label: 'Short only', value: 'short_only' },
];
const engineOptions: SelectOption[] = [
  { label: 'Vectorized', value: 'vectorized' }, { label: 'Event driven', value: 'event_driven' },
];
const gapOptions: SelectOption[] = [
  { label: 'Skip', value: 'skip' }, { label: 'Expire', value: 'expire' },
  { label: 'Error', value: 'error' },
];
const exitOptions: SelectOption[] = [
  { label: 'Conservative', value: 'conservative' },
  { label: 'Stop first', value: 'stop_first' },
  { label: 'Take profit first', value: 'take_profit_first' },
  { label: 'Error', value: 'error' },
];

watch(draft, (value) => {
  store.creationDraft = JSON.parse(JSON.stringify(value)) as BacktestRequestPayload;
}, { deep: true, immediate: true });

function initialDraft(): DraftRequest {
  const end = new Date();
  const start = new Date(end.getTime() - 30 * 86_400_000);
  return {
    symbols: [], exchange: null, timeframe: 'M1',
    start_ms: Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate()),
    end_ms: Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), end.getUTCDate()),
    strategy: { strategy_id: '', parameters: {} },
    initial_capital: 10_000, engine: 'vectorized', data_granularity: 'bar',
    persist_result: false, run_metadata: null,
    execution: {
      signal_timing: 'close', fill_timing: 'next_open', price_source: 'open',
      allow_partial_fills: false, allowed_directions: 'long_and_short',
      trade_accounting_policy: 'average_cost', gap_policy: 'skip',
      intrabar_exit_policy: 'conservative', commission_bps: 0, slippage_bps: 0,
    },
  };
}

async function loadCatalog(): Promise<void> {
  catalogError.value = null;
  try {
    catalog.value = await fetchStrategyCatalog();
    if (!catalog.value.length) throw new Error('No registered strategies are available.');
    if (!draft.value.strategy.strategy_id) selectStrategy(catalog.value[0].strategy_id);
  } catch (error) {
    catalogError.value = error instanceof Error ? error.message : 'Unknown catalog error';
  }
}

function selectStrategy(strategyId: string): void {
  const selected = catalog.value.find((entry) => entry.strategy_id === strategyId);
  if (!selected) return;
  draft.value.strategy = { strategy_id: selected.strategy_id,
    strategy_version: selected.strategy_version, parameters: defaults(selected) };
  fieldErrors.value = {};
}

function useCurrentVersion(): void {
  const selected = selectedStrategy.value;
  if (!selected) return;
  const retained = Object.fromEntries(selected.parameters.filter((parameter) =>
    Object.hasOwn(draft.value.strategy.parameters, parameter.name))
    .map((parameter) => [parameter.name, draft.value.strategy.parameters[parameter.name]]));
  draft.value.strategy = {
    strategy_id: selected.strategy_id, strategy_version: selected.strategy_version,
    parameters: { ...defaults(selected), ...retained },
  };
  submitError.value = null;
}

function defaults(strategy: StrategyCatalogEntry): Record<string, null | boolean | number | string> {
  return Object.fromEntries(strategy.parameters.filter((parameter) => 'default' in parameter)
    .map((parameter) => [parameter.name, parameter.default])) as Record<string, null | boolean | number | string>;
}

function parameterOptions(parameter: StrategyParameterSchema): SelectOption[] {
  return choiceValues(parameter).map((value, index) => ({
    label: value === null ? 'Null' : String(value),
    value: index,
  }));
}

function choiceValues(parameter: StrategyParameterSchema): (null | boolean | number | string)[] {
  const values = parameter.type === 'bool' ? [true, false] : parameter.choices ?? [];
  return parameter.nullable ? [...values, null] : values;
}

function selectValue(parameter: StrategyParameterSchema): number | null {
  const value = draft.value.strategy.parameters[parameter.name];
  const index = choiceValues(parameter).findIndex((choice) => choice === value);
  return index < 0 ? null : index;
}

function setChoice(parameter: StrategyParameterSchema, value: number): void {
  setParameter(parameter.name, choiceValues(parameter)[value]);
}

function setParameter(name: string, value: unknown): void {
  draft.value.strategy.parameters[name] = value as null | boolean | number | string;
  delete fieldErrors.value[name];
}

function numberValue(name: string): number | null {
  const value = draft.value.strategy.parameters[name];
  return typeof value === 'number' ? value : null;
}

function stringValue(name: string): string {
  const value = draft.value.strategy.parameters[name];
  return typeof value === 'string' ? value : '';
}

function selectMarket(symbolId: number): void {
  const market = markets.all.find((item) => item.symbol_id === symbolId);
  if (!market) return;
  draft.value.symbols = [market.symbol];
  draft.value.exchange = market.exchange;
  delete fieldErrors.value.market;
}

function dateValue(timestamp: number): string {
  return Number.isFinite(timestamp) ? new Date(timestamp).toISOString().slice(0, 10) : '';
}

function setDate(field: 'start_ms' | 'end_ms', event: Event): void {
  const value = (event.target as HTMLInputElement).value;
  draft.value[field] = value ? Date.parse(`${value}T00:00:00Z`) : 0;
  delete fieldErrors.value.dates;
}

async function submit(): Promise<void> {
  fieldErrors.value = {};
  submitError.value = null;
  if (!marketValue.value) fieldErrors.value.market = 'Select an available Market.';
  if (draft.value.start_ms <= 0 || draft.value.end_ms <= 0 ||
      draft.value.start_ms >= draft.value.end_ms) {
    fieldErrors.value.dates = 'End date must be after start date.';
  }
  if (typeof draft.value.initial_capital !== 'number' ||
      !Number.isFinite(draft.value.initial_capital) || draft.value.initial_capital <= 0) {
    fieldErrors.value.capital = 'Initial capital must be greater than zero.';
  }
  for (const parameter of selectedStrategy.value?.parameters ?? []) {
    if (parameter.required && !Object.hasOwn(draft.value.strategy.parameters, parameter.name)) {
      fieldErrors.value[parameter.name] = 'This parameter is required.';
    } else if (draft.value.strategy.parameters[parameter.name] === null && !parameter.nullable) {
      fieldErrors.value[parameter.name] = 'This parameter cannot be null.';
    }
  }
  if (selectedStrategy.value?.strategy_version !== draft.value.strategy.strategy_version) {
    submitError.value = 'Review the current strategy version before submitting.';
  }
  if (Object.keys(fieldErrors.value).length || submitError.value) return;
  submitting.value = true;
  try {
    emit('submitted', await submitBacktestRun(draft.value));
    emit('update:show', false);
  } catch (error) {
    if (error instanceof BacktestSubmissionError) {
      if (error.code === 'strategy_version_unavailable') {
        submitError.value = 'Strategy version changed. Review the refreshed catalog before submitting again.';
        await loadCatalog();
      } else {
        for (const field of error.fields) fieldErrors.value[field] = error.message;
        submitError.value = error.message;
      }
    } else {
      submitError.value = error instanceof Error ? error.message : 'Submission failed.';
    }
  } finally {
    submitting.value = false;
  }
}

onMounted(() => {
  if (markets.all.length && !draft.value.symbols.length) {
    selectMarket(markets.all[0].symbol_id);
  } else if (!markets.all.length) {
    void markets.fetch().then(() => {
      if (!draft.value.symbols.length && markets.all.length) selectMarket(markets.all[0].symbol_id);
    }).catch(() => { fieldErrors.value.market = 'Market options unavailable.'; });
  }
  void loadCatalog();
});
</script>

<style scoped>
.creation-fields { display: grid; gap: 12px; padding-bottom: 24px; }
.creation-fields label { display: grid; gap: 4px; }
.creation-fields small { color: #aeb8c8; }
.creation-fields [role='alert'] { color: #ffb4b4; }
.creation-fields details { display: grid; padding-top: 8px; }
.creation-fields details label { margin-top: 12px; }
.creation-fields input[type='date'] { color: inherit; background: #232934; border: 1px solid #555; border-radius: 4px; padding: 8px; }
</style>
