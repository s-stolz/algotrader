<template>
  <BaseDrawer :show="show" width="min(100vw, max(720px, 66.667vw))" @update:show="emit('update:show', $event)">
    <n-drawer-content :title="isSweep ? 'Review Parameter Sweep' : 'Create standalone Backtest'" closable>
      <p v-if="catalogError" role="alert">Strategy catalog unavailable. {{ catalogError }}</p>
      <n-button v-if="catalogError" @click="loadCatalog">Retry catalog</n-button>
      <template v-if="draft && catalog.length">
        <p v-if="store.reuseSource" data-testid="reuse-source">
          Editing a new {{ store.reuseSource.kind === 'run' ? 'Backtest' : 'Parameter Sweep' }}
          from saved {{ store.reuseSource.kind }} {{ store.reuseSource.id }}. The saved history stays unchanged.
        </p>
        <p
          v-if="store.reuseSource && !selectedStrategy &&
            draft.strategy.strategy_id === store.reuseSource.strategyId"
          role="alert"
          data-testid="reuse-removed-strategy"
        >
          Strategy {{ store.reuseSource.strategyId }} is no longer registered. This saved record
          remains inspectable. Choose a current strategy to create new work.
        </p>
        <p
          v-if="store.reuseSource && selectedStrategy && strategyNeedsReview"
          role="alert"
          data-testid="reuse-version-review"
        >
          Saved {{ store.reuseSource.strategyId }} version
          {{ store.reuseSource.strategyVersion ?? 'unavailable (legacy request)' }};
          current version {{ selectedStrategy.strategy_version }}. Review parameter changes and
          invalid values before submitting. This is a new experiment, not an exact reproduction.
          <n-button size="small" data-testid="reuse-use-current" @click="useCurrentVersion">
            Use current version
          </n-button>
        </p>
        <p v-for="change in parameterChanges" :key="change" role="status">{{ change }}</p>
        <div class="creation-fields">
          <label>Run type
            <BaseSelect
              :value="isSweep ? 'sweep' : 'standalone'"
              :options="runTypeOptions"
              data-testid="creation-run-type"
              @update:value="setRunType"
            />
          </label>
          <label>
            <span class="strategy-label">Strategy
              <n-tag v-if="selectedStrategy" size="small" round :bordered="false">
                Version {{ selectedStrategy.strategy_version }}
              </n-tag>
            </span>
            <BaseSelect
              :value="draft.strategy.strategy_id"
              :options="strategyOptions"
              data-testid="creation-strategy"
              @update:value="selectStrategy"
            />
          </label>
          <p
            v-if="!store.reuseSource && selectedStrategy && strategyNeedsReview"
            role="alert"
          >
            Strategy version changed. Review the current schema before submitting.
            <n-button size="small" @click="useCurrentVersion">Use current version</n-button>
          </p>
          <section class="parameters-section" aria-labelledby="parameters-heading">
            <h3 id="parameters-heading">Strategy parameters</h3>
            <div class="parameters-grid">
              <div v-for="parameter in selectedStrategy?.parameters ?? []" :key="parameter.name" class="parameter-field">
                <label class="parameter-label" :for="`parameter-${parameter.name}`">
                  <span>{{ parameter.display_name || parameter.name }}<span v-if="parameter.required"> *</span></span>
                  <small
                    v-if="parameter.minimum !== undefined || parameter.maximum !== undefined"
                    class="parameter-constraints"
                  >
                    <span v-if="parameter.minimum !== undefined">
                      {{ parameter.exclusive_minimum ? '>' : '≥' }} {{ parameter.minimum }}
                    </span>
                    <span v-if="parameter.maximum !== undefined">
                      {{ parameter.exclusive_maximum ? '<' : '≤' }} {{ parameter.maximum }}
                    </span>
                  </small>
                </label>
                <BaseSelect
                  v-if="isSweep"
                  size="small"
                  class="parameter-mode"
                  :aria-label="`${parameter.display_name || parameter.name} mode`"
                  :value="sweepParameter(parameter).mode"
                  :options="parameterModeOptions(parameter)"
                  :data-testid="`sweep-mode-${parameter.name}`"
                  @update:value="sweepParameter(parameter).mode = $event"
                />
                <BaseSelect
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
                  <BaseSelect
                    v-if="parameter.choices || parameter.type === 'bool'"
                    multiple
                    :value="selectedChoiceIndexes(parameter)"
                    :options="parameterOptions(parameter)"
                    :data-testid="`sweep-values-${parameter.name}`"
                    @update:value="setSweepChoices(parameter, $event)"
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
                  <BaseCheckbox
                    v-if="parameter.nullable && !parameter.choices && parameter.type !== 'bool'"
                    v-model:checked="sweepParameter(parameter).includeNull"
                  >Include null</BaseCheckbox>
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
                  class="null-button"
                  @click="setParameter(parameter.name, null)"
                >Set null</n-button>
                <small v-if="parameter.nullable && draft.strategy.parameters[parameter.name] === null">
                  Null selected
                </small>
                <small v-if="parameter.description">{{ parameter.description }}</small>
                <small v-if="fieldErrors[parameter.name]" role="alert">{{ fieldErrors[parameter.name] }}</small>
              </div>
            </div>
          </section>
          <section class="settings-section" aria-labelledby="market-period-heading">
            <h3 id="market-period-heading">Market &amp; period</h3>
            <p class="section-description">Choose the historical data for your backtest. Dates use UTC.</p>
            <div class="settings-grid">
              <div class="field-group">
                <label v-if="!isSweep">Market
                  <BaseSelect
                    :value="marketValue"
                    :options="marketOptions"
                    data-testid="creation-market"
                    @update:value="selectMarket"
                  />
                </label>
                <label v-else>Markets
                  <BaseSelect
                    v-model:value="sweep.marketIds"
                    multiple
                    :options="marketOptions"
                    data-testid="sweep-markets"
                  />
                </label>
                <small v-if="!marketOptions.length" role="alert">Market options unavailable.</small>
                <small v-if="missingMarkets.length" role="alert" data-testid="reuse-missing-market">
                  Saved Market{{ missingMarkets.length === 1 ? '' : 's' }}
                  {{ missingMarkets.join(', ') }} unavailable. Remove or replace before preview/submission.
                </small>
                <small v-if="fieldErrors.market" role="alert">{{ fieldErrors.market }}</small>
              </div>
              <div class="field-group">
                <label v-if="!isSweep">Timeframe
                  <BaseSelect
                    v-model:value="draft.timeframe"
                    :options="timeframeOptions"
                    data-testid="creation-timeframe"
                  />
                </label>
                <label v-else>Timeframes
                  <BaseSelect
                    v-model:value="sweep.timeframes"
                    multiple
                    :options="timeframeOptions"
                    data-testid="sweep-timeframes"
                  />
                </label>
              </div>
              <label>Start date (UTC)
                <n-date-picker
                  type="date"
                  value-format="yyyy-MM-dd"
                  :formatted-value="dateValue(draft.start_ms)"
                  :clearable="false"
                  :input-readonly="true"
                  data-testid="creation-start"
                  @update:formatted-value="setDate('start_ms', $event)"
                />
              </label>
              <label>End date (UTC)
                <n-date-picker
                  type="date"
                  value-format="yyyy-MM-dd"
                  :formatted-value="dateValue(draft.end_ms)"
                  :clearable="false"
                  :input-readonly="true"
                  data-testid="creation-end"
                  @update:formatted-value="setDate('end_ms', $event)"
                />
              </label>
              <small v-if="fieldErrors.dates" class="full-width" role="alert">{{ fieldErrors.dates }}</small>
            </div>
          </section>
          <section class="settings-section" aria-labelledby="capital-heading">
            <h3 id="capital-heading">Capital &amp; execution</h3>
            <p class="section-description">Set the starting balance and simulation assumptions.</p>
            <div class="capital-field field-group">
              <label>Initial capital
                <n-input-number
                  v-model:value="draft.initial_capital"
                  :min="0.01"
                  data-testid="creation-capital"
                />
              </label>
              <small v-if="fieldErrors.capital" role="alert">{{ fieldErrors.capital }}</small>
            </div>
            <details class="execution-settings">
              <summary>Execution settings</summary>
              <div class="execution-group">
                <h4>Trading rules</h4>
                <div class="settings-grid">
                  <label v-if="!isSweep">Allowed Directions
                    <BaseSelect
                      v-model:value="draft.execution.allowed_directions"
                      :options="directionOptions"
                      data-testid="creation-directions"
                    />
                  </label>
                  <label v-else>Allowed Directions
                    <BaseSelect
                      v-model:value="sweep.allowedDirections"
                      multiple
                      :options="directionOptions"
                      data-testid="sweep-directions"
                    />
                  </label>
                  <label>Engine
                    <BaseSelect v-model:value="draft.engine" :options="engineOptions" />
                  </label>
                </div>
              </div>
              <div class="execution-group">
                <h4>Trading costs</h4>
                <p class="section-description">Costs are in basis points: 1 bp = 0.01%.</p>
                <div class="settings-grid">
                  <label>Commission (bps)
                    <n-input-number v-model:value="draft.execution.commission_bps" :min="0" />
                  </label>
                  <label>Slippage (bps)
                    <n-input-number v-model:value="draft.execution.slippage_bps" :min="0" />
                  </label>
                </div>
              </div>
              <div class="execution-group">
                <h4>Data &amp; fills</h4>
                <div class="settings-grid">
                  <label>Gap policy
                    <BaseSelect v-model:value="draft.execution.gap_policy" :options="gapOptions" />
                  </label>
                  <label>Intrabar exit policy
                    <BaseSelect v-model:value="draft.execution.intrabar_exit_policy" :options="exitOptions" />
                  </label>
                </div>
              </div>
            </details>
          </section>
        </div>
        <p v-if="submitError" role="alert">{{ submitError }}</p>
        <section v-if="isSweep" class="preview-section" aria-labelledby="preview-heading">
          <div class="section-header">
            <h3 id="preview-heading">Sweep preview</h3>
            <n-tag v-if="sweepLimit" size="small" :bordered="false">Limit: {{ sweepLimit }} candidates</n-tag>
          </div>
          <p v-if="previewError" role="alert">{{ previewError }}</p>
          <p v-if="previewPending" role="status">Refreshing preview…</p>
          <section v-if="preview" class="preview-review" data-testid="sweep-review">
            <dl class="preview-counts">
              <div><dt>Raw candidates</dt><dd>{{ preview.raw_count }}</dd></div>
              <div><dt>Ready</dt><dd>{{ preview.ready_count }}</dd></div>
              <div><dt>Excluded</dt><dd>{{ preview.excluded_count }}</dd></div>
            </dl>
            <p class="section-description">Candidate # preserves the full grid order. Ready member # is contiguous after exclusions.
              Sorting and filtering only change this review table.</p>
            <label class="preview-filter">Status
              <BaseSelect
                v-model:value="previewFilter"
                :options="previewFilterOptions"
                data-testid="sweep-filter"
              />
            </label>
            <BaseDataTable
              :columns="previewColumns"
              :data="filteredCandidates"
              :pagination="{ pageSize: 20 }"
              :scroll-x="previewColumns.length * 150"
              data-testid="sweep-candidates"
            />
          </section>
        </section>
      </template>
      <template #footer>
        <n-button
          v-if="draft && catalog.length && !isSweep"
          type="primary"
          :disabled="submitting || !marketOptions.length || !!catalogError || !selectedStrategy ||
            strategyNeedsReview"
          :loading="submitting"
          data-testid="creation-submit"
          @click="submit"
        >Create Backtest</n-button>
        <n-button
          v-else-if="isSweep && sweepAcceptanceEnabled"
          type="primary"
          :disabled="submitting || previewPending || !preview || !!previewError ||
            strategyNeedsReview || parameterIssues.length > 0 || missingMarkets.length > 0"
          :loading="submitting"
          data-testid="sweep-submit"
          @click="submitSweep"
        >Accept Batch</n-button>
        <span v-else-if="isSweep">Parameter Sweep submission becomes available with batch execution.</span>
      </template>
    </n-drawer-content>
  </BaseDrawer>
              </template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue';
import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import BaseCheckbox from '@/components/Common/BaseCheckbox.vue';
import BaseDrawer from '@/components/Common/BaseDrawer.vue';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import { NButton, NDatePicker, NDrawerContent, NInput, NInputNumber, NTag } from 'naive-ui';
import type { DataTableColumns, SelectOption } from 'naive-ui';
import { BacktestSubmissionError, fetchStrategyCatalog, fetchSweepCapabilities,
  previewParameterSweep, submitBacktestBatch, submitBacktestRun } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import type { BacktestRequestPayload, StrategyCatalogEntry, StrategyParameterSchema,
  SweepDraftState, SweepParameterDraft, SweepPreview, SweepPreviewCandidate,
  SweepPreviewRequest, SweepParameterAxis } from '@/types/backtesterContracts';
import { TIMEFRAME_CODES } from '@/types/contracts';
import type { ReuseSource } from './backtestReuse';

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
const strategyNeedsReview = computed(() => !selectedStrategy.value ||
  selectedStrategy.value.strategy_version !== draft.value.strategy.strategy_version);
const missingMarkets = computed(() => isSweep.value
  ? sweep.value.marketIds.filter((id) => !markets.all.some((market) => market.symbol_id === id))
    .map((id) => `ID ${id}`)
  : draft.value.symbols.length && marketValue.value === undefined
    ? [`${draft.value.exchange ?? ''}:${draft.value.symbols.join(', ')}`] : []);
const parameterIssues = computed(() => {
  const selected = selectedStrategy.value;
  if (!selected) return [];
  return selected.parameters.flatMap((parameter) => {
    const axis = isSweep.value ? sweep.value.parameters[parameter.name] : undefined;
    if (axis && axis.mode !== 'constant') {
      if (axis.mode === 'range') return parameterModeOptions(parameter).some((mode) =>
        mode.value === 'range') ? [] : [`${parameter.name}: range is unavailable`];
      return (axis.selectedChoiceValues ?? []).flatMap((value) => {
        const issue = parameterIssue(parameter, value);
        return issue ? [`${parameter.name}: ${issue}`] : [];
      });
    }
    const value = draft.value.strategy.parameters[parameter.name];
    const issue = parameterIssue(parameter, value);
    return issue ? [`${parameter.name}: ${issue}`] : [];
  });
});
const parameterChanges = computed(() => {
  const source = store.reuseSource as ReuseSource | null;
  if (!source || !selectedStrategy.value) return [];
  const old = source.historicalMetadata;
  const oldNames = old?.parameters.map((parameter) => parameter.name) ??
    Object.keys(draft.value.strategy.parameters);
  const newNames = selectedStrategy.value.parameters.map((parameter) => parameter.name);
  const changes = [
    ...newNames.filter((name) => !oldNames.includes(name)).map((name) => `New parameter: ${name}`),
    ...oldNames.filter((name) => !newNames.includes(name)).map((name) => `Removed parameter: ${name}`),
    ...parameterIssues.value.map((issue) => `Invalid copied value: ${issue}`),
  ];
  if (old) for (const parameter of selectedStrategy.value.parameters) {
    const previous = old.parameters.find((item) => item.name === parameter.name);
    if (previous && !sameParameterSchema(previous, parameter)) {
      let described = false;
      if (JSON.stringify(previous.default) !== JSON.stringify(parameter.default)) {
        changes.push(`${parameter.name} default changed: ${JSON.stringify(previous.default)} → ` +
          JSON.stringify(parameter.default));
        described = true;
      }
      if (JSON.stringify(previous.choices) !== JSON.stringify(parameter.choices)) {
        changes.push(`${parameter.name} choices changed: ${JSON.stringify(previous.choices ?? [])} → ` +
          JSON.stringify(parameter.choices ?? []));
        described = true;
      }
      if (previous.type !== parameter.type) {
        changes.push(`${parameter.name} type changed: ${previous.type} → ${parameter.type}`);
        described = true;
      }
      if (!described) changes.push(`Changed parameter contract: ${parameter.name}`);
    }
  }
  if (!old && strategyNeedsReview.value) for (const parameter of selectedStrategy.value.parameters) {
    const saved = draft.value.strategy.parameters[parameter.name];
    if (saved !== undefined && 'default' in parameter &&
      JSON.stringify(saved) !== JSON.stringify(parameter.default)) {
      changes.push(`${parameter.name}: saved value ${JSON.stringify(saved)}; ` +
        `current default ${JSON.stringify(parameter.default)}.`);
    }
  }
  return changes;
});

function sameParameterSchema(left: StrategyParameterSchema, right: StrategyParameterSchema): boolean {
  const keys = new Set([...Object.keys(left), ...Object.keys(right)]);
  return [...keys].every((key) => JSON.stringify(left[key as keyof StrategyParameterSchema]) ===
    JSON.stringify(right[key as keyof StrategyParameterSchema]));
}
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

watch(() => store.reuseRevision, () => {
  draft.value = store.creationDraft
    ? JSON.parse(JSON.stringify(store.creationDraft)) as DraftRequest : initialDraft();
  sweep.value = store.creationSweepDraft
    ? JSON.parse(JSON.stringify(store.creationSweepDraft)) as SweepDraftState : {
    isSweep: false, marketIds: [], timeframes: [], allowedDirections: [], parameters: {},
  };
  fieldErrors.value = {};
  submitError.value = null;
  submissionId = globalThis.crypto.randomUUID();
  if (!draft.value.symbols.length && !store.reuseSource && markets.all.length) {
    selectMarket(markets.all[0].symbol_id);
  }
});

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

function selectedChoiceIndexes(parameter: StrategyParameterSchema): number[] {
  const input = sweepParameter(parameter);
  if (!input.selectedChoiceValues) return input.choiceIndexes;
  return input.selectedChoiceValues.map((value) => choiceValues(parameter).findIndex(
    (choice) => choice === value)).filter((index) => index >= 0);
}

function setSweepChoices(parameter: StrategyParameterSchema, indexes: number[]): void {
  const input = sweepParameter(parameter);
  input.choiceIndexes = indexes;
  input.selectedChoiceValues = indexes.map((index) => choiceValues(parameter)[index]);
}

function parameterIssue(parameter: StrategyParameterSchema, value: unknown): string | null {
  if (value === undefined) return parameter.required ? 'This parameter is required.' : null;
  if (value === null) return parameter.nullable ? null : 'null is unavailable';
  const correctType = parameter.type === 'bool' ? typeof value === 'boolean' :
    parameter.type === 'str' ? typeof value === 'string' :
      typeof value === 'number' && Number.isFinite(value) &&
      (parameter.type !== 'int' || Number.isInteger(value));
  if (!correctType) return `expected ${parameter.type}`;
  if (parameter.choices && !parameter.choices.includes(value as number | string)) {
    return `${JSON.stringify(value)} is not a current choice`;
  }
  if (typeof value === 'number') {
    if (parameter.minimum !== undefined && (parameter.exclusive_minimum
      ? value <= parameter.minimum : value < parameter.minimum)) return 'below current minimum';
    if (parameter.maximum !== undefined && (parameter.exclusive_maximum
      ? value >= parameter.maximum : value > parameter.maximum)) return 'above current maximum';
  }
  return null;
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
  if (missingMarkets.value.length) throw new Error('Replace unavailable saved Markets.');
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
        values = (input.selectedChoiceValues ?? input.choiceIndexes.map(
          (index) => choiceValues(parameter)[index])) as Array<null | boolean | number | string>;
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
    Object.hasOwn(draft.value.strategy.parameters, parameter.name) &&
    !store.reuseSource?.defaultedParameters.includes(parameter.name))
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

function setDate(field: 'start_ms' | 'end_ms', value: string | null): void {
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
    const issue = parameterIssue(parameter, draft.value.strategy.parameters[parameter.name]);
    if (issue) fieldErrors.value[parameter.name] = issue;
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
  if (!store.reuseSource && markets.all.length && !draft.value.symbols.length) {
    selectMarket(markets.all[0].symbol_id);
  } else if (!markets.all.length) {
    void markets.fetch().then(() => {
      if (!store.reuseSource && !draft.value.symbols.length && markets.all.length) {
        selectMarket(markets.all[0].symbol_id);
      }
    }).catch(() => { fieldErrors.value.market = 'Market options unavailable.'; });
  }
  void loadCatalog();
});
</script>

<style scoped>
.creation-fields { display: grid; gap: 20px; padding: 8px 0 28px; }
.creation-fields label, .preview-filter { display: grid; gap: 8px; min-width: 0; font-size: 13px; font-weight: 500; }
.strategy-label { display: flex; align-items: center; gap: 10px; }
.parameters-section { margin-top: 8px; }
.creation-fields h3, .preview-section h3 { margin: 0 0 14px; font-size: 16px; font-weight: 600; letter-spacing: -0.2px; }
.settings-section { padding: 20px; border: 1px solid #ffffff12; border-radius: 8px; }
.settings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr)); gap: 20px 24px; }
.field-group { display: grid; align-content: start; gap: 8px; min-width: 0; }
.full-width { grid-column: 1 / -1; }
.section-description { margin: -6px 0 20px; color: #aeb8c8; font-size: 12px; line-height: 1.6; font-weight: normal; }
.capital-field { max-width: 320px; }
.execution-settings { margin-top: 24px; }
.execution-group { margin-top: 24px; }
.execution-group h4 { margin: 0 0 12px; font-size: 13px; font-weight: 600; }
.section-header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.section-header h3 { margin: 0; }
.preview-section { border-top: 1px solid #ffffff12; padding-top: 24px; }
.preview-counts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 0 0 24px; }
.preview-counts > div { display: flex; flex-direction: column; gap: 6px; padding: 14px; background: #ffffff05; border-radius: 8px; }
.preview-counts dt { color: #aeb8c8; font-size: 12px; }
.preview-counts dd { margin: 0; font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; }
.preview-filter { max-width: 220px; margin-bottom: 16px; }
.preview-section [role='alert'] { color: #ffb4b4; }
.parameters-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(280px, 100%), 1fr)); gap: 16px; }
.parameter-field { display: flex; flex-direction: column; gap: 10px; min-width: 0; padding: 16px; border: 1px solid #ffffff12; border-radius: 8px; background: #ffffff03; }
.creation-fields .parameter-label { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; }
.parameter-label > span { overflow-wrap: anywhere; }
.parameter-mode { max-width: 140px; }
.null-button { align-self: flex-start; }
.parameter-constraints { display: inline-flex; gap: 8px; margin-left: auto; font-weight: normal; }
.parameter-constraints span { white-space: nowrap; }
.creation-fields small { color: #aeb8c8; font-size: 12px; line-height: 1.5; }
.creation-fields [role='alert'] { color: #ffb4b4; }
.creation-fields details { padding-top: 16px; border-top: 1px solid #ffffff12; }
.creation-fields summary { cursor: pointer; font-size: 14px; font-weight: 600; }
.creation-fields :deep(.n-date-picker) { width: 100%; }
.range-inputs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.preview-review { min-width: 0; }
.preview-review :deep(.n-data-table-th) { white-space: nowrap; }
.string-values { display: grid; gap: 8px; }
.string-value { display: flex; gap: 8px; align-items: start; }
.string-value .n-input { flex: 1; }
</style>
