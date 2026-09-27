<template>
  <n-drawer :show="show" :width="isSweep && preview ? 'min(1100px, 100vw)' : 'min(540px, 100vw)'" @update:show="emit('update:show', $event)">
    <n-drawer-content :title="isSweep ? 'Review Parameter Sweep' : 'Create standalone Backtest'" closable>
      <p v-if="catalogError" role="alert">Strategy catalog unavailable. {{ catalogError }}</p>
      <n-button v-if="catalogError" @click="loadCatalog">Retry catalog</n-button>
      <template v-if="draft && catalog.length">
        <div class="creation-fields">
          <label>Run type
            <n-select
              :value="isSweep ? 'sweep' : 'standalone'"
              :options="runTypeOptions"
              data-testid="creation-run-type"
              @update:value="setRunType"
            />
          </label>
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
              v-if="isSweep"
              :value="sweepParameter(parameter).mode"
              :options="parameterModeOptions(parameter)"
              :data-testid="`sweep-mode-${parameter.name}`"
              @update:value="sweepParameter(parameter).mode = $event"
            />
            <n-select
              v-if="(!isSweep || sweepParameter(parameter).mode === 'constant') &&
                (parameter.choices || parameter.type === 'bool')"
              :id="`parameter-${parameter.name}`"
              :value="selectValue(parameter)"
              :options="parameterOptions(parameter)"
              :data-testid="`creation-param-${parameter.name}`"
              @update:value="setChoice(parameter, $event)"
            />
            <n-input-number
              v-else-if="(!isSweep || sweepParameter(parameter).mode === 'constant') &&
                (parameter.type === 'int' || parameter.type === 'float')"
              :id="`parameter-${parameter.name}`"
              :value="numberValue(parameter.name)"
              :min="parameter.minimum"
              :max="parameter.maximum"
              :precision="parameter.type === 'int' ? 0 : undefined"
              :data-testid="`creation-param-${parameter.name}`"
              @update:value="setParameter(parameter.name, $event)"
            />
            <n-input
              v-else-if="!isSweep || sweepParameter(parameter).mode === 'constant'"
              :id="`parameter-${parameter.name}`"
              :value="stringValue(parameter.name)"
              :data-testid="`creation-param-${parameter.name}`"
              @update:value="setParameter(parameter.name, $event)"
            />
            <template v-else-if="sweepParameter(parameter).mode === 'values'">
              <n-select
                v-if="parameter.choices || parameter.type === 'bool'"
                multiple
                :value="sweepParameter(parameter).choiceIndexes"
                :options="parameterOptions(parameter)"
                :data-testid="`sweep-values-${parameter.name}`"
                @update:value="sweepParameter(parameter).choiceIndexes = $event"
              />
              <div v-else-if="parameter.type === 'str'" class="string-values">
                <div v-for="(value, index) in stringValues(parameter)" :key="index" class="string-value">
                  <n-input
                    type="textarea"
                    :value="value"
                    :aria-label="`${parameter.display_name || parameter.name} value ${index + 1}`"
                    :data-testid="`sweep-string-${parameter.name}-${index}`"
                    @update:value="stringValues(parameter)[index] = $event"
                  />
                  <n-button
                    size="small"
                    :data-testid="`sweep-remove-${parameter.name}-${index}`"
                    @click="stringValues(parameter).splice(index, 1)"
                  >Remove value</n-button>
                </div>
                <n-button
                  size="small"
                  :data-testid="`sweep-add-${parameter.name}`"
                  @click="stringValues(parameter).push('')"
                >Add string value</n-button>
                <small>Each field is one exact string. An empty field is an empty string.</small>
              </div>
              <n-input
                v-else
                type="textarea"
                :value="sweepParameter(parameter).valuesText"
                placeholder="One numeric value per line"
                :data-testid="`sweep-values-${parameter.name}`"
                @update:value="sweepParameter(parameter).valuesText = $event"
              />
              <n-checkbox
                v-if="parameter.nullable && !parameter.choices && parameter.type !== 'bool'"
                v-model:checked="sweepParameter(parameter).includeNull"
              >Include null</n-checkbox>
            </template>
            <div v-else-if="sweepParameter(parameter).mode === 'range'" class="range-inputs">
              <label>Start<n-input-number
                v-model:value="sweepParameter(parameter).rangeStart"
                :precision="parameter.type === 'int' ? 0 : undefined"
              /></label>
              <label>Stop<n-input-number
                v-model:value="sweepParameter(parameter).rangeStop"
                :precision="parameter.type === 'int' ? 0 : undefined"
              /></label>
              <label>Step<n-input-number
                v-model:value="sweepParameter(parameter).rangeStep"
                :precision="parameter.type === 'int' ? 0 : undefined"
              /></label>
            </div>
            <n-button
              v-if="(!isSweep || sweepParameter(parameter).mode === 'constant') &&
                parameter.nullable && !parameter.choices && parameter.type !== 'bool'"
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
          <label v-if="!isSweep">Market
            <n-select
              :value="marketValue"
              :options="marketOptions"
              data-testid="creation-market"
              @update:value="selectMarket"
            />
          </label>
          <label v-else>Markets
            <n-select
              v-model:value="sweep.marketIds"
              multiple
              :options="marketOptions"
              data-testid="sweep-markets"
            />
          </label>
          <small v-if="!marketOptions.length" role="alert">Market options unavailable.</small>
          <small v-if="fieldErrors.market" role="alert">{{ fieldErrors.market }}</small>
          <label v-if="!isSweep">Timeframe
            <n-select
              v-model:value="draft.timeframe"
              :options="timeframeOptions"
              data-testid="creation-timeframe"
            />
          </label>
          <label v-else>Timeframes
            <n-select
              v-model:value="sweep.timeframes"
              multiple
              :options="timeframeOptions"
              data-testid="sweep-timeframes"
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
            <label v-if="!isSweep">Allowed Directions
              <n-select
                v-model:value="draft.execution.allowed_directions"
                :options="directionOptions"
                data-testid="creation-directions"
              />
            </label>
            <label v-else>Allowed Directions
              <n-select
                v-model:value="sweep.allowedDirections"
                multiple
                :options="directionOptions"
                data-testid="sweep-directions"
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
        <template v-if="isSweep">
          <p v-if="sweepLimit">Current raw candidate limit: {{ sweepLimit }}.</p>
          <p v-if="previewError" role="alert">{{ previewError }}</p>
          <p v-if="previewPending" role="status">Refreshing preview…</p>
          <section v-if="preview" class="preview-review" data-testid="sweep-review">
            <p>{{ preview.raw_count }} raw candidates · {{ preview.ready_count }} Ready ·
              {{ preview.excluded_count }} Excluded. Limit: {{ preview.max_sweep_candidate_count }}.</p>
            <p>Candidate # preserves the full grid order. Ready member # is contiguous after exclusions.
              Sorting and filtering only change this review table.</p>
            <label>Status
              <n-select
                v-model:value="previewFilter"
                :options="previewFilterOptions"
                data-testid="sweep-filter"
              />
            </label>
            <n-data-table
              :columns="previewColumns"
              :data="filteredCandidates"
              :pagination="{ pageSize: 20 }"
              :bordered="false"
              data-testid="sweep-candidates"
            />
          </section>
        </template>
      </template>
      <template #footer>
        <n-button
          v-if="draft && catalog.length && !isSweep"
          :disabled="submitting || !marketOptions.length || !!catalogError"
          :loading="submitting"
          data-testid="creation-submit"
          @click="submit"
        >Create Backtest</n-button>
        <n-button
          v-else-if="isSweep && sweepAcceptanceEnabled"
          :disabled="submitting || previewPending || !preview || !!previewError"
          :loading="submitting"
          data-testid="sweep-submit"
          @click="submitSweep"
        >Accept Batch</n-button>
        <span v-else-if="isSweep">Parameter Sweep submission becomes available with batch execution.</span>
      </template>
    </n-drawer-content>
  </n-drawer>
              </template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue';
import { NButton, NCheckbox, NDataTable, NDrawer, NDrawerContent, NInput, NInputNumber, NSelect } from 'naive-ui';
import type { DataTableColumns, SelectOption } from 'naive-ui';
import { BacktestSubmissionError, fetchStrategyCatalog, fetchSweepCapabilities,
  previewParameterSweep, submitBacktestBatch, submitBacktestRun } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { BacktestRequestPayload, StrategyCatalogEntry, StrategyParameterSchema,
  SweepDraftState, SweepParameterDraft, SweepPreview, SweepPreviewCandidate,
  SweepPreviewRequest, SweepParameterAxis } from '@/types/backtesterContracts';
import { TIMEFRAME_CODES } from '@/types/contracts';

type DraftRequest = Omit<BacktestRequestPayload, 'strategy' | 'run_metadata'> & {
  strategy: { strategy_id: string; strategy_version?: number; parameters: Record<string, null | boolean | number | string> };
  run_metadata: null;
};

defineProps<{ show: boolean }>();
const emit = defineEmits<{
  'update:show': [show: boolean]; submitted: [runId: string]; 'submitted-batch': [batchId: string];
}>();
const store = useBacktestWorkspaceStore();
const markets = useMarketsStore();
const draft = ref<DraftRequest>((store.creationDraft as DraftRequest | null) ?? initialDraft());
const sweep = ref<SweepDraftState>(store.creationSweepDraft ?? {
  isSweep: false, marketIds: [], timeframes: [], allowedDirections: [], parameters: {},
});
const isSweep = computed(() => sweep.value.isSweep);
const catalog = shallowRef<StrategyCatalogEntry[]>([]);
const catalogError = ref<string | null>(null);
const submitError = ref<string | null>(null);
const fieldErrors = ref<Record<string, string>>({});
const submitting = ref(false);
const preview = shallowRef<SweepPreview | null>(null);
const previewPending = ref(false);
const previewError = ref<string | null>(null);
const sweepLimit = ref<number | null>(null);
const sweepAcceptanceEnabled = ref(false);
let submissionId = globalThis.crypto.randomUUID();
const previewFilter = ref<'all' | 'ready' | 'excluded'>('all');
const previewFilterOptions: SelectOption[] = [
  { label: 'All', value: 'all' }, { label: 'Ready', value: 'ready' },
  { label: 'Excluded', value: 'excluded' },
];
const runTypeOptions: SelectOption[] = [
  { label: 'Standalone Backtest', value: 'standalone' },
  { label: 'Parameter Sweep', value: 'sweep' },
];
let previewRevision = 0;
let previewTimer: ReturnType<typeof setTimeout> | undefined;
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
watch(sweep, (value) => {
  store.creationSweepDraft = JSON.parse(JSON.stringify(value)) as SweepDraftState;
}, { deep: true, immediate: true });

watch(isSweep, (enabled) => {
  if (!enabled) return;
  void fetchSweepCapabilities().then((capabilities) => {
    sweepLimit.value = capabilities.max_sweep_candidate_count;
    sweepAcceptanceEnabled.value = capabilities.batch_acceptance_enabled;
  }).catch(() => { sweepLimit.value = null; });
}, { immediate: true });

watch([draft, sweep, catalog, () => markets.all], () => {
  previewRevision += 1;
  submissionId = globalThis.crypto.randomUUID();
  if (previewTimer) clearTimeout(previewTimer);
  preview.value = null;
  previewPending.value = false;
  previewError.value = null;
  if (!isSweep.value || !selectedStrategy.value) return;
  let request: SweepPreviewRequest;
  try {
    request = buildSweepRequest();
  } catch (error) {
    previewError.value = error instanceof Error ? error.message : 'Complete the sweep inputs.';
    return;
  }
  const revision = previewRevision;
  previewPending.value = true;
  previewTimer = setTimeout(() => { void refreshPreview(request, revision); }, 150);
}, { deep: true });

onUnmounted(() => {
  previewRevision += 1;
  if (previewTimer) clearTimeout(previewTimer);
});

const filteredCandidates = computed(() => preview.value?.candidates.filter((row) =>
  previewFilter.value === 'all' || row.status === previewFilter.value) ?? []);
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
function compareRows(a: SweepPreviewCandidate, b: SweepPreviewCandidate,
  select: (row: SweepPreviewCandidate) => unknown): number {
  const left = select(a);
  const right = select(b);
  const compared = typeof left === 'number' && typeof right === 'number' ? left - right :
    collator.compare(String(left ?? ''), String(right ?? ''));
  return compared || a.candidate_ordinal - b.candidate_ordinal;
}
const previewColumns = computed<DataTableColumns<SweepPreviewCandidate>>(() => [
  { title: 'Candidate #', key: 'candidate_ordinal', sorter: (a, b) =>
    a.candidate_ordinal - b.candidate_ordinal, render: (row) => String(row.candidate_ordinal + 1) },
  { title: 'Market', key: 'market', sorter: (a, b) => compareRows(a, b, (row) =>
    `${row.market.symbol} ${row.market.exchange}`), render: (row) =>
    `${row.market.symbol} · ${row.market.exchange}` },
  { title: 'Timeframe', key: 'timeframe', sorter: (a, b) => compareRows(a, b, (row) =>
    TIMEFRAME_CODES.indexOf(row.timeframe as typeof TIMEFRAME_CODES[number])),
  },
  ...(selectedStrategy.value?.parameters ?? []).map((parameter) => ({
    title: parameter.display_name || parameter.name, key: `param-${parameter.name}`,
    sorter: (a: SweepPreviewCandidate, b: SweepPreviewCandidate) => compareRows(a, b,
      (row) => row.parameters[parameter.name]),
    render: (row: SweepPreviewCandidate) => String(row.parameters[parameter.name]),
  })),
  { title: 'Allowed Directions', key: 'allowed_directions', sorter: (a, b) =>
    compareRows(a, b, (row) => row.allowed_directions) },
  { title: 'State', key: 'status', sorter: (a, b) => compareRows(a, b, (row) => row.status),
    render: (row) => row.status === 'ready' ? `Ready · member #${(row.member_ordinal ?? 0) + 1}` :
      `Excluded · ${row.issues?.map((issue) => issue.message).join('; ') ?? ''}` },
]);

function sweepParameter(parameter: StrategyParameterSchema): SweepParameterDraft {
  return sweep.value.parameters[parameter.name] ??= {
    mode: 'constant', valuesText: '', stringValues: [], choiceIndexes: [], includeNull: false,
    rangeStart: null, rangeStop: null, rangeStep: null,
  };
}

function stringValues(parameter: StrategyParameterSchema): string[] {
  const input = sweepParameter(parameter);
  return input.stringValues ??= input.valuesText === '' ? [] : input.valuesText.split('\n');
}

function parameterModeOptions(parameter: StrategyParameterSchema): SelectOption[] {
  const modes: SelectOption[] = [
    { label: 'Constant', value: 'constant' }, { label: 'Values', value: 'values' },
  ];
  if ((parameter.type === 'int' || parameter.type === 'float') && !parameter.choices) {
    modes.push({ label: 'Range', value: 'range' });
  }
  return modes;
}

function setRunType(value: string): void {
  sweep.value.isSweep = value === 'sweep';
  if (sweep.value.isSweep) {
    if (!sweep.value.marketIds.length && marketValue.value !== undefined) {
      sweep.value.marketIds = [marketValue.value];
    }
    if (!sweep.value.timeframes.length) sweep.value.timeframes = [draft.value.timeframe];
    if (!sweep.value.allowedDirections.length) {
      sweep.value.allowedDirections = [draft.value.execution.allowed_directions];
    }
  }
}

function buildSweepRequest(): SweepPreviewRequest {
  const selected = selectedStrategy.value;
  if (!selected || selected.strategy_version !== draft.value.strategy.strategy_version) {
    throw new Error('Review the current Strategy Version.');
  }
  if (!sweep.value.marketIds.length || !sweep.value.timeframes.length ||
      !sweep.value.allowedDirections.length) {
    throw new Error('Select at least one Market, Timeframe, and Allowed Directions value.');
  }
  if (draft.value.start_ms <= 0 || draft.value.end_ms <= draft.value.start_ms ||
      !Number.isFinite(draft.value.initial_capital) || draft.value.initial_capital <= 0) {
    throw new Error('Enter valid dates and initial capital.');
  }
  const parameter_axes: Record<string, SweepParameterAxis> = {};
  for (const parameter of selected.parameters) {
    const input = sweepParameter(parameter);
    if (input.mode === 'constant') {
      const value = draft.value.strategy.parameters[parameter.name];
      if (value === undefined) {
        if (parameter.required) throw new Error(`${parameter.name} is required.`);
        continue;
      }
      parameter_axes[parameter.name] = { mode: 'constant', value };
    } else if (input.mode === 'range') {
      if (input.rangeStart === null || input.rangeStop === null || input.rangeStep === null) {
        throw new Error(`Enter Start, Stop, and Step for ${parameter.name}.`);
      }
      parameter_axes[parameter.name] = { mode: 'range', start: input.rangeStart,
        stop: input.rangeStop, step: input.rangeStep };
    } else {
      let values: Array<null | boolean | number | string>;
      if (parameter.choices || parameter.type === 'bool') {
        values = input.choiceIndexes.map((index) => choiceValues(parameter)[index]);
      } else if (parameter.type === 'str') {
        values = [...stringValues(parameter)];
      } else {
        values = input.valuesText === '' ? [] : input.valuesText.split('\n').map((line) => {
          if (!line.trim()) throw new Error(`Enter numeric values for ${parameter.name}.`);
          const value: unknown = JSON.parse(line);
          if (typeof value !== 'number' || !Number.isFinite(value)) {
            throw new Error(`Enter numeric values for ${parameter.name}.`);
          }
          return value;
        });
      }
      if (input.includeNull) values.push(null);
      if (!values.length || values.some((value) => value === undefined)) {
        throw new Error(`Select at least one value for ${parameter.name}.`);
      }
      parameter_axes[parameter.name] = { mode: 'values', values };
    }
  }
  const { symbols: _symbols, timeframe: _timeframe, exchange: _exchange, ...shared } = draft.value;
  return { ...shared, strategy: { strategy_id: selected.strategy_id,
    strategy_version: selected.strategy_version },
    markets: sweep.value.marketIds, timeframes: sweep.value.timeframes,
    parameter_axes, allowed_directions: sweep.value.allowedDirections };
}

async function refreshPreview(request: SweepPreviewRequest, revision: number): Promise<void> {
  try {
    const result = await previewParameterSweep(request);
    if (revision !== previewRevision) return;
    preview.value = result;
    sweepLimit.value = result.max_sweep_candidate_count;
  } catch (error) {
    if (revision !== previewRevision) return;
    previewError.value = error instanceof Error ? error.message : 'Sweep preview failed.';
    if (error instanceof BacktestSubmissionError && error.code === 'strategy_version_unavailable') {
      await loadCatalog();
    }
  } finally {
    if (revision === previewRevision) previewPending.value = false;
  }
}

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

async function submitSweep(): Promise<void> {
  if (!preview.value || previewPending.value || previewError.value || submitting.value) return;
  submitting.value = true;
  submitError.value = null;
  try {
    const request = buildSweepRequest();
    const batchId = await submitBacktestBatch(request, submissionId);
    emit('submitted-batch', batchId);
    emit('update:show', false);
  } catch (error) {
    if (error instanceof BacktestSubmissionError) {
      submitError.value = error.message;
      if (error.code === 'strategy_version_unavailable') await loadCatalog();
    } else {
      submitError.value = error instanceof Error ? error.message : 'Batch submission failed.';
    }
    const revision = ++previewRevision;
    preview.value = null;
    previewPending.value = true;
    try {
      await refreshPreview(buildSweepRequest(), revision);
    } catch {
      previewPending.value = false;
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
.string-values { display: grid; gap: 8px; }
.string-value { display: flex; gap: 8px; align-items: start; }
.string-value .n-input { flex: 1; }
</style>
