<template>
  <BaseStepModal
    :show="show"
    title="Create Backtest"
    :steps="['Setup', 'Parameters', 'Review']"
    :step="step"
    :fill-body="step === 2"
    @update:step="navigateStep"
    @update:show="emit('update:show', $event)"
  >
    <p v-if="catalogPending" role="status">Loading strategies…</p>
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
      <div v-show="step !== 2" class="creation-fields">
        <div v-show="step === 0" class="setup-fields">
          <label>Experiment name (optional)
            <n-input
              v-model:value="draft.name"
              data-testid="creation-name"
              placeholder="Enter an experiment name"
              :status="nameIssue ? 'error' : undefined"
            />
          </label>
          <p v-if="nameIssue" role="alert">{{ nameIssue }}</p>
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
          <section class="market-period" aria-label="Market and period">
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
                    max-tag-count="responsive"
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
                    max-tag-count="responsive"
                    :options="timeframeOptions"
                    data-testid="sweep-timeframes"
                  />
                </label>
              </div>
              <BaseDateRange
                class="full-width"
                :start="dateValue(draft.start_ms)"
                :end="dateValue(draft.end_ms)"
                @update:start="setDate('start_ms', $event)"
                @update:end="setDate('end_ms', $event)"
              />
              <small v-if="fieldErrors.dates" class="full-width" role="alert">{{ fieldErrors.dates }}</small>
            </div>
          </section>
          <label>Initial capital
            <n-input-number v-model:value="draft.initial_capital" :min="0.01" data-testid="creation-capital" />
          </label>
          <small v-if="fieldErrors.capital" role="alert">{{ fieldErrors.capital }}</small>
          <BacktestExecutionFields v-model:execution="draft.execution" v-model:engine="draft.engine" />
        </div>
        <section v-show="step === 1" class="parameters-section" aria-label="Strategy parameters">
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
                @update:value="changeParameterMode(parameter, $event)"
              />
              <BaseSelect
                v-if="(!isSweep || sweepParameter(parameter).mode === 'constant') &&
                  (parameter.choices || parameter.type === 'bool')"
                :id="`parameter-${parameter.name}`"
                :input-props="{ 'aria-label': parameter.display_name || parameter.name }"
                :value="selectValue(parameter)"
                :options="parameterOptions(parameter)"
                :data-testid="`creation-param-${parameter.name}`"
                @update:value="setChoice(parameter, $event)"
              />
              <n-input-number
                v-else-if="(!isSweep || sweepParameter(parameter).mode === 'constant') &&
                  (parameter.type === 'int' || parameter.type === 'float')"
                :id="`parameter-${parameter.name}`"
                :input-props="{ 'aria-label': parameter.display_name || parameter.name }"
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
                :input-props="{ 'aria-label': parameter.display_name || parameter.name }"
                :value="stringValue(parameter.name)"
                :data-testid="`creation-param-${parameter.name}`"
                @update:value="setParameter(parameter.name, $event)"
              />
              <template v-else-if="sweepParameter(parameter).mode === 'values'">
                <BaseSelect
                  v-if="parameter.choices || parameter.type === 'bool'"
                  multiple
                  max-tag-count="responsive"
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
                <BaseNumberValues
                  v-else
                  :value="numericValues(parameter)"
                  :label="`${parameter.display_name || parameter.name} values`"
                  :integer="parameter.type === 'int'"
                  :data-testid="`sweep-values-${parameter.name}`"
                  @update:value="setNumericValues(parameter, $event)"
                  @update:valid="numericEntryValid[parameter.name] = $event"
                />
                <BaseCheckbox
                  v-if="parameter.nullable && !parameter.choices && parameter.type !== 'bool'"
                  v-model:checked="sweepParameter(parameter).includeNull"
                >Include null</BaseCheckbox>
              </template>
              <div v-else-if="sweepParameter(parameter).mode === 'range'" class="range-inputs">
                <label>Start<n-input-number
                  :input-props="{ 'aria-label': `${parameter.display_name || parameter.name} start` }"
                  :data-testid="`sweep-start-${parameter.name}`"
                  v-model:value="sweepParameter(parameter).rangeStart"
                  :precision="parameter.type === 'int' ? 0 : undefined"
                /></label>
                <label>Stop (inclusive)<n-input-number
                  :input-props="{ 'aria-label': `${parameter.display_name || parameter.name} stop` }"
                  :data-testid="`sweep-stop-${parameter.name}`"
                  v-model:value="sweepParameter(parameter).rangeStop"
                  :precision="parameter.type === 'int' ? 0 : undefined"
                /></label>
                <label>Step<n-input-number
                  :input-props="{ 'aria-label': `${parameter.display_name || parameter.name} step` }"
                  :data-testid="`sweep-step-${parameter.name}`"
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
      </div>
      <p v-if="fieldErrors.timeframe" role="alert">{{ fieldErrors.timeframe }}</p>
      <p v-if="fieldErrors.strategy" role="alert">{{ fieldErrors.strategy }}</p>
      <p v-if="submitError" role="alert">{{ submitError }}</p>
      <BaseDataTable
        v-if="!isSweep && step === 2"
        :columns="standaloneColumns"
        :data="[draft]"
        :scroll-x="550 + (selectedStrategy?.parameters.length ?? 0) * 135"
        size="small"
      />
      <section v-if="isSweep" v-show="step === 2" class="preview-section" aria-label="Sweep preview">
        <div class="section-header">
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
            :pagination="{ pageSize: 10 }"
            size="small"
            flex-height
            :scroll-x="previewColumns.length * 150"
            data-testid="sweep-candidates"
          />
        </section>
      </section>
    </template>
    <template #footer>
      <div class="creation-footer">
        <n-tag round :bordered="false" :type="isSweep && !preview?.ready_count ? 'warning' : 'success'">
          {{ isSweep ? `${preview?.raw_count ?? 0} candidates` : '1 run' }}
        </n-tag>
        <div class="creation-actions">
          <n-button v-if="step > 0" @click="navigateStep(step - 1)">Back</n-button>
          <n-button v-if="step < 2" type="primary" @click="navigateStep(step + 1)">
            {{ step === 0 ? 'Parameters →' : 'Review candidates →' }}
          </n-button>
          <div v-show="step === 2">
            <n-button
              v-if="draft && catalog.length && !isSweep"
              type="primary"
              :disabled="submitting || !marketOptions.length || !!catalogError || !selectedStrategy ||
                strategyNeedsReview || !!nameIssue"
              :loading="submitting"
              data-testid="creation-submit"
              @click="submit"
            >Create Backtest</n-button>
            <n-button
              v-else-if="isSweep && sweepAcceptanceEnabled"
              type="primary"
              :disabled="submitting || previewPending || !preview || !!previewError ||
                strategyNeedsReview || parameterIssues.length > 0 || missingMarkets.length > 0 || !preview.ready_count || hasPendingNumericEntry"
              :loading="submitting"
              data-testid="sweep-submit"
              @click="submitSweep"
            >Accept Batch</n-button>
            <span v-else-if="isSweep">Parameter Sweep submission becomes available with batch execution.</span>
          </div></div></div>
    </template>
  </BaseStepModal>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue';
import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import BaseCheckbox from '@/components/Common/BaseCheckbox.vue';
import BaseStepModal from '@/components/Common/BaseStepModal.vue';
import BaseNumberValues from '@/components/Common/BaseNumberValues.vue';
import BaseDateRange from '@/components/Common/BaseDateRange.vue';
import BacktestExecutionFields from './BacktestExecutionFields.vue';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import { NButton, NInput, NInputNumber, NTag } from 'naive-ui';
import type { DataTableColumns, SelectOption } from 'naive-ui';
import { BacktestSubmissionError, fetchStrategyCatalog, fetchSweepCapabilities,
  previewParameterSweep, submitBacktestBatch, submitBacktestRun } from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import { normalizeExperimentName } from '@/types/backtesterContracts';
import type { BacktestRequestPayload, StrategyCatalogEntry, StrategyParameterSchema,
  SweepDraftState, SweepParameterDraft, SweepPreview, SweepPreviewCandidate,
  SweepPreviewRequest, SweepParameterAxis } from '@/types/backtesterContracts';
import { TIMEFRAME_CODES } from '@/types/contracts';
import type { ReuseSource } from './backtestReuse';

type DraftRequest = Omit<BacktestRequestPayload, 'strategy' | 'run_metadata'> & {
  strategy: { strategy_id: string; strategy_version?: number; parameters: Record<string, null | boolean | number | string> };
  run_metadata: null;
  name?: string;
};

defineProps<{ show: boolean }>();
const emit = defineEmits<{
  'update:show': [show: boolean]; submitted: [runId: string]; 'submitted-batch': [batchId: string];
}>();
const step = ref(0);
const numericEntryValid = ref<Record<string, boolean>>({});
function navigateStep(next: number): void {
  if (next > step.value) {
    fieldErrors.value = {};
    if (!validateSetup()) { step.value = 0; return; }
    if (next === 2 && !validateParameters()) { step.value = 1; return; }
  }
  step.value = next;
}
function validateSetup(): boolean {
  if (nameIssue.value) fieldErrors.value.name = nameIssue.value;
  if (strategyNeedsReview.value) fieldErrors.value.strategy = 'Review the current Strategy Version.';
  if (isSweep.value ? !sweep.value.marketIds.length || missingMarkets.value.length : !marketValue.value) {
    fieldErrors.value.market = 'Select an available Market.';
  }
  if (isSweep.value && !sweep.value.timeframes.length) fieldErrors.value.timeframe = 'Select at least one Timeframe.';
  if (!Number.isFinite(draft.value.start_ms) || !Number.isFinite(draft.value.end_ms) ||
    draft.value.start_ms <= 0 || draft.value.end_ms <= draft.value.start_ms) {
    fieldErrors.value.dates = 'End date must be after start date.';
  }
  if (!Number.isFinite(draft.value.initial_capital) || draft.value.initial_capital <= 0) {
    fieldErrors.value.capital = 'Initial capital must be greater than zero.';
  }
  return !Object.keys(fieldErrors.value).length;
}
function validateParameters(): boolean {
  if (isSweep.value) {
    try { buildSweepRequest(); }
    catch (error) { submitError.value = error instanceof Error ? error.message : 'Complete parameter values.'; return false; }
    if (hasPendingNumericEntry.value) { submitError.value = 'Finish adding or clear the numeric value.'; return false; }
  }
  for (const parameter of selectedStrategy.value?.parameters ?? []) {
    if (isSweep.value && sweepParameter(parameter).mode !== 'constant') continue;
    const issue = parameterIssue(parameter, draft.value.strategy.parameters[parameter.name]);
    if (issue) fieldErrors.value[parameter.name] = issue;
  }
  return !Object.keys(fieldErrors.value).length;
}
const store = useBacktestWorkspaceStore();
const markets = useMarketsStore();
const draft = ref<DraftRequest>((store.creationDraft as DraftRequest | null) ?? initialDraft());
const sweep = ref<SweepDraftState>(store.creationSweepDraft ?? {
  isSweep: false, marketIds: [], timeframes: [], allowedDirections: [], parameters: {},
});
if (sweep.value.allowedDirections.length) {
  draft.value.execution.allowed_directions = sweep.value.allowedDirections[0];
}
const hasPendingNumericEntry = computed(() => Object.entries(numericEntryValid.value).some(
  ([name, valid]) => !valid && sweep.value.parameters[name]?.mode === 'values'));
const isSweep = computed(() => sweep.value.isSweep);
const nameIssue = computed(() => {
  try { normalizeExperimentName(draft.value.name); return null; }
  catch (error) { return error instanceof Error ? error.message : 'Invalid experiment name.'; }
});
const catalog = shallowRef<StrategyCatalogEntry[]>([]);
const catalogError = ref<string | null>(null);
const catalogPending = ref(false);
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

watch(draft, (value) => {
  store.creationDraft = JSON.parse(JSON.stringify(value)) as BacktestRequestPayload;
  if (sweep.value.allowedDirections.length !== 1 || sweep.value.allowedDirections[0] !== value.execution.allowed_directions) {
    sweep.value.allowedDirections = [value.execution.allowed_directions];
  }
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
  step.value = 0;
  numericEntryValid.value = {};
  if (sweep.value.allowedDirections.length) {
    draft.value.execution.allowed_directions = sweep.value.allowedDirections[0];
  }
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
function reviewParameterValue(parameter: StrategyParameterSchema, value: unknown): string {
  if (value === undefined) {
    return 'default' in parameter ? `${reviewParameterValue(parameter, parameter.default)} (default)` : 'Not set';
  }
  return typeof value === 'string' ? JSON.stringify(value) : String(value);
}
const standaloneColumns = computed<DataTableColumns<DraftRequest>>(() => [
  { title: '#', key: 'ordinal', width: 55, fixed: 'left', render: () => '1' },
  { title: 'Market', key: 'market', width: 150, render: row => `${row.symbols.join(', ')} · ${row.exchange}` },
  { title: 'Timeframe', key: 'timeframe', width: 100 },
  { title: 'Directions', key: 'direction', width: 145, render: row => row.execution.allowed_directions },
  ...(selectedStrategy.value?.parameters ?? []).map(parameter => ({
    title: parameter.display_name || parameter.name, key: parameter.name, width: 135,
    render: (row: DraftRequest) => reviewParameterValue(parameter, row.strategy.parameters[parameter.name]),
  })),
]);
const previewColumns = computed<DataTableColumns<SweepPreviewCandidate>>(() => [
  { title: '#', key: 'candidate_ordinal', width: 65, fixed: 'left', sorter: (a, b) =>
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

function changeParameterMode(parameter: StrategyParameterSchema, mode: SweepParameterDraft['mode']): void {
  sweepParameter(parameter).mode = mode;
  numericEntryValid.value[parameter.name] = true;
  if (mode === 'constant' && (parameter.type === 'int' || parameter.type === 'float') && !parameter.choices) {
    delete draft.value.strategy.parameters[parameter.name];
  }
}

function numericValues(parameter: StrategyParameterSchema): number[] {
  return sweepParameter(parameter).valuesText.split('\n').filter(Boolean).map(Number);
}

function setNumericValues(parameter: StrategyParameterSchema, values: number[]): void {
  sweepParameter(parameter).valuesText = values.map(String).join('\n');
  delete sweepParameter(parameter).selectedChoiceValues;
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
    { label: 'Fixed', value: 'constant' }, { label: 'Values', value: 'values' },
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
  if (!sweep.value.marketIds.length || !sweep.value.timeframes.length) {
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
  const { symbols: _symbols, timeframe: _timeframe, exchange: _exchange, name: _name, ...shared } = draft.value;
  return { ...shared, strategy: { strategy_id: selected.strategy_id,
    strategy_version: selected.strategy_version },
    markets: sweep.value.marketIds, timeframes: sweep.value.timeframes,
    parameter_axes, allowed_directions: [draft.value.execution.allowed_directions] };
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
    persist_result: false, run_metadata: null, name: '',
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
  catalogPending.value = true;
  try {
    catalog.value = await fetchStrategyCatalog();
    if (!catalog.value.length) throw new Error('No registered strategies are available.');
    if (!draft.value.strategy.strategy_id) selectStrategy(catalog.value[0].strategy_id);
  } catch (error) {
    catalogError.value = error instanceof Error ? error.message : 'Unknown catalog error';
  } finally { catalogPending.value = false; }
}

function selectStrategy(strategyId: string): void {
  const selected = catalog.value.find((entry) => entry.strategy_id === strategyId);
  if (!selected) return;
  draft.value.strategy = { strategy_id: selected.strategy_id,
    strategy_version: selected.strategy_version, parameters: defaults(selected) };
  fieldErrors.value = {};
  numericEntryValid.value = {};
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
  if (!validateSetup()) { step.value = 0; return; }
  if (!validateParameters()) { step.value = 1; return; }
  submitting.value = true;
  try {
    emit('submitted', await submitBacktestRun({ ...draft.value, name: normalizeExperimentName(draft.value.name) }));
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
  if (nameIssue.value) { submitError.value = nameIssue.value; return; }
  if (!preview.value?.ready_count || previewPending.value || previewError.value || submitting.value || hasPendingNumericEntry.value) return;
  submitting.value = true;
  submitError.value = null;
  try {
    const request = buildSweepRequest();
    const batchId = await submitBacktestBatch(request, submissionId, normalizeExperimentName(draft.value.name));
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
.creation-fields, .setup-fields { display: grid; gap: 18px; min-width: 0; }
.creation-fields label, .preview-filter { display: grid; gap: 7px; min-width: 0; font-size: 12px; }
.strategy-label { display: flex; align-items: center; gap: 10px; }
.settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.field-group { display: grid; gap: 8px; min-width: 0; }
.full-width { grid-column: 1 / -1; }
.parameters-grid { display: flex; flex-direction: column; gap: 16px; }
.parameter-field { display: grid; grid-template-columns: 1fr auto; gap: 8px 16px; padding-bottom: 16px; border-bottom: 1px solid var(--surface-border); min-width: 0; }
.parameter-field > :not(.parameter-label):not(.parameter-mode) { grid-column: 1 / -1; }
.parameter-label { align-content: center; font-weight: 600; }
.parameter-mode { width: 110px; }
.parameter-constraints { display: inline-flex; gap: 8px; }
small { color: #98a5b5; font-size: 12px; }
[role='alert'] { color: #ffb4b4; }
.range-inputs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.string-values { display: grid; gap: 8px; }
.string-value { display: flex; gap: 8px; align-items: start; }
.string-value .n-input { flex: 1; }
.preview-section { display: flex; flex-direction: column; gap: 8px; min-width: 0; height: 100%; }
.preview-review { display: flex; flex-direction: column; flex: 1; min-height: 260px; }
.preview-review :deep(.base-data-table) { flex: 1; min-height: 0; }
.preview-counts { display: flex; gap: 24px; margin: 8px 0; font-size: 12px; }
.preview-counts > div { display: flex; gap: 6px; }
.preview-counts dd { margin: 0; }
.preview-filter { max-width: 200px; margin: 12px 0; }
.section-description { color: #98a5b5; font-size: 12px; }
.preview-review :deep(.n-data-table-th) { white-space: nowrap; }
.creation-footer, .creation-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
@media (max-width: 520px) {
  .settings-grid, .range-inputs { grid-template-columns: 1fr; }
  .creation-footer { flex-wrap: wrap; gap: 8px; }
  .creation-actions { margin-left: auto; max-width: 100%; }
}
</style>
