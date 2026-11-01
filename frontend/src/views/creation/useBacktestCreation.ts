import { useCreationNavigation } from './useCreationNavigation';
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue';
import type { SelectOption } from 'naive-ui';
import {
  BacktestSubmissionError,
  fetchStrategyCatalog,
  fetchSweepCapabilities,
  previewParameterSweep,
  submitBacktestBatch,
  submitBacktestRun,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import { normalizeExperimentName } from '@/types/backtesterContracts';
import type {
  BacktestRequestPayload,
  StrategyCatalogEntry,
  SweepDraftState,
  SweepPreview,
  SweepPreviewRequest,
} from '@/types/backtesterContracts';
import type { ReuseSource } from '../backtestReuse';
import { applyCurrentStrategy } from './creationStrategyMigration';
import { creationFields } from './creationFields';
import {
  experimentNameIssue,
  parameterIssue,
  parameterModeOptions,
  defaults,
} from './creationParameters';
import {
  initialDraft,
  buildSweepRequest as createSweepRequest,
  type DraftRequest,
} from './creationRequest';
import { parameterChanges as describeParameterChanges } from './creationStrategyReview';

export interface CreationEvents {
  (event: 'submitted', runId: string): void;
  (event: 'submitted-batch', batchId: string): void;
  (event: 'update:show', show: boolean): void;
}
export function useBacktestCreation(emit: CreationEvents) {
  const store = useBacktestWorkspaceStore();
  const markets = useMarketsStore();
  const draft = ref<DraftRequest>(
    (store.creationDraft as DraftRequest | null) ?? initialDraft(),
  );
  const sweep = ref<SweepDraftState>(
    store.creationSweepDraft ?? {
      isSweep: false,
      marketIds: [],
      timeframes: [],
      allowedDirections: [],
      parameters: {},
    },
  );
  if (sweep.value.allowedDirections.length) {
    draft.value.execution.allowed_directions = sweep.value.allowedDirections[0];
  }
  const isSweep = computed(() => sweep.value.isSweep);
  const nameIssue = computed(() => experimentNameIssue(draft.value.name));
  const catalog = shallowRef<StrategyCatalogEntry[]>([]);
  const catalogPending = ref(false);
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
  let previewRevision = 0;
  let previewTimer: ReturnType<typeof setTimeout> | undefined;
  const selectedStrategy = computed(() =>
    catalog.value.find(
      (entry) => entry.strategy_id === draft.value.strategy.strategy_id,
    ),
  );
  const strategyNeedsReview = computed(
    () =>
      !selectedStrategy.value ||
      selectedStrategy.value.strategy_version !==
        draft.value.strategy.strategy_version,
  );
  const missingMarkets = computed(() =>
    isSweep.value
      ? sweep.value.marketIds
          .filter(
            (id) => !markets.all.some((market) => market.symbol_id === id),
          )
          .map((id) => `ID ${id}`)
      : draft.value.symbols.length && marketValue.value === undefined
        ? [`${draft.value.exchange ?? ''}:${draft.value.symbols.join(', ')}`]
        : [],
  );
  const parameterIssues = computed(() => {
    const selected = selectedStrategy.value;
    if (!selected) return [];
    return selected.parameters.flatMap((parameter) => {
      const axis = isSweep.value
        ? sweep.value.parameters[parameter.name]
        : undefined;
      if (axis && axis.mode !== 'constant') {
        if (axis.mode === 'range')
          return parameterModeOptions(parameter).some(
            (mode) => mode.value === 'range',
          )
            ? []
            : [`${parameter.name}: range is unavailable`];
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

  const strategyOptions = computed<SelectOption[]>(() =>
    catalog.value.map((entry) => ({
      label: `${entry.display_name} · v${entry.strategy_version}`,
      value: entry.strategy_id,
    })),
  );
  const fields = creationFields(draft, sweep, fieldErrors, markets);
  const { marketValue, sweepParameter, stringValues, selectMarket } = fields;
  const parameterChanges = computed(() =>
    describeParameterChanges(
      store.reuseSource as ReuseSource | null,
      selectedStrategy.value,
      draft.value,
      store.reuseSource?.strategyVersion !==
        selectedStrategy.value?.strategy_version,
    ),
  );
  const {
    step,
    navigateStep,
    numericEntryValid,
    hasPendingNumericEntry,
    changeParameterMode,
    numericValues,
    setNumericValues,
    validateSetup,
    validateParameters,
  } = useCreationNavigation({
    draft,
    sweep,
    isSweep,
    nameIssue,
    strategyNeedsReview,
    missingMarkets,
    marketValue,
    selectedStrategy,
    fieldErrors,
    submitError,
    sweepParameter,
    buildSweepRequest,
  });
  function buildSweepRequest() {
    return createSweepRequest(
      draft.value,
      sweep.value,
      selectedStrategy.value,
      missingMarkets.value,
      sweepParameter,
      stringValues,
    );
  }

  watch(
    draft,
    (value) => {
      store.creationDraft = JSON.parse(
        JSON.stringify(value),
      ) as BacktestRequestPayload;
      if (
        sweep.value.allowedDirections.length !== 1 ||
        sweep.value.allowedDirections[0] !== value.execution.allowed_directions
      ) {
        sweep.value.allowedDirections = [value.execution.allowed_directions];
      }
    },
    { deep: true, immediate: true },
  );
  watch(
    sweep,
    (value) => {
      store.creationSweepDraft = JSON.parse(
        JSON.stringify(value),
      ) as SweepDraftState;
    },
    { deep: true, immediate: true },
  );

  watch(
    () => store.reuseRevision,
    () => {
      draft.value = store.creationDraft
        ? (JSON.parse(JSON.stringify(store.creationDraft)) as DraftRequest)
        : initialDraft();
      sweep.value = store.creationSweepDraft
        ? (JSON.parse(
            JSON.stringify(store.creationSweepDraft),
          ) as SweepDraftState)
        : {
            isSweep: false,
            marketIds: [],
            timeframes: [],
            allowedDirections: [],
            parameters: {},
          };
      if (store.reuseSource && strategyNeedsReview.value) useCurrentVersion();
      step.value = 0;
      numericEntryValid.value = {};
      if (sweep.value.allowedDirections.length)
        draft.value.execution.allowed_directions =
          sweep.value.allowedDirections[0];
      fieldErrors.value = {};
      submitError.value = null;
      submissionId = globalThis.crypto.randomUUID();
      if (
        !draft.value.symbols.length &&
        !store.reuseSource &&
        markets.all.length
      ) {
        selectMarket(markets.all[0].symbol_id);
      }
    },
  );

  watch(
    isSweep,
    (enabled) => {
      if (!enabled) return;
      void fetchSweepCapabilities()
        .then((capabilities) => {
          sweepLimit.value = capabilities.max_sweep_candidate_count;
          sweepAcceptanceEnabled.value = capabilities.batch_acceptance_enabled;
        })
        .catch(() => {
          sweepLimit.value = null;
        });
    },
    { immediate: true },
  );

  watch(
    [draft, sweep, catalog, () => markets.all],
    () => {
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
        previewError.value =
          error instanceof Error ? error.message : 'Complete the sweep inputs.';
        return;
      }
      const revision = previewRevision;
      previewPending.value = true;
      previewTimer = setTimeout(() => {
        void refreshPreview(request, revision);
      }, 150);
    },
    { deep: true },
  );

  onUnmounted(() => {
    previewRevision += 1;
    if (previewTimer) clearTimeout(previewTimer);
  });

  async function refreshPreview(
    request: SweepPreviewRequest,
    revision: number,
  ): Promise<void> {
    try {
      const result = await previewParameterSweep(request);
      if (revision !== previewRevision) return;
      preview.value = result;
      sweepLimit.value = result.max_sweep_candidate_count;
    } catch (error) {
      if (revision !== previewRevision) return;
      previewError.value =
        error instanceof Error ? error.message : 'Sweep preview failed.';
      if (
        error instanceof BacktestSubmissionError &&
        error.code === 'strategy_version_unavailable'
      ) {
        await loadCatalog();
      }
    } finally {
      if (revision === previewRevision) previewPending.value = false;
    }
  }

  async function loadCatalog(): Promise<void> {
    catalogError.value = null;
    catalogPending.value = true;
    try {
      catalog.value = await fetchStrategyCatalog();
      if (!catalog.value.length)
        throw new Error('No registered strategies are available.');
      if (!draft.value.strategy.strategy_id)
        selectStrategy(catalog.value[0].strategy_id);
      if (store.reuseSource && strategyNeedsReview.value) useCurrentVersion();
    } catch (error) {
      catalogError.value =
        error instanceof Error ? error.message : 'Unknown catalog error';
    } finally {
      catalogPending.value = false;
    }
  }

  function selectStrategy(strategyId: string): void {
    const selected = catalog.value.find(
      (entry) => entry.strategy_id === strategyId,
    );
    if (!selected) return;
    draft.value.strategy = {
      strategy_id: selected.strategy_id,
      strategy_version: selected.strategy_version,
      parameters: defaults(selected),
    };
    fieldErrors.value = {};
    numericEntryValid.value = {};
  }

  function useCurrentVersion(): void {
    const selected = selectedStrategy.value;
    if (!selected) return;
    applyCurrentStrategy(
      selected,
      draft.value,
      sweep.value,
      store.reuseSource as ReuseSource | null,
    );
    submitError.value = null;
  }

  async function submit(): Promise<void> {
    fieldErrors.value = {};
    submitError.value = null;
    if (!validateSetup()) {
      step.value = 0;
      return;
    }
    if (!validateParameters()) {
      step.value = 1;
      return;
    }
    submitting.value = true;
    try {
      emit(
        'submitted',
        await submitBacktestRun({
          ...draft.value,
          name: normalizeExperimentName(draft.value.name),
        }),
      );
      emit('update:show', false);
    } catch (error) {
      if (error instanceof BacktestSubmissionError) {
        if (error.code === 'strategy_version_unavailable') {
          submitError.value =
            'Strategy version changed. Review the refreshed catalog before submitting again.';
          await loadCatalog();
        } else {
          for (const field of error.fields)
            fieldErrors.value[field] = error.message;
          submitError.value = error.message;
        }
      } else {
        submitError.value =
          error instanceof Error ? error.message : 'Submission failed.';
      }
    } finally {
      submitting.value = false;
    }
  }

  async function submitSweep(): Promise<void> {
    if (nameIssue.value) {
      submitError.value = nameIssue.value;
      return;
    }
    if (
      !preview.value?.ready_count ||
      previewPending.value ||
      previewError.value ||
      submitting.value ||
      hasPendingNumericEntry.value
    )
      return;
    submitting.value = true;
    submitError.value = null;
    try {
      const request = buildSweepRequest();
      const batchId = await submitBacktestBatch(
        request,
        submissionId,
        normalizeExperimentName(draft.value.name),
      );
      emit('submitted-batch', batchId);
      emit('update:show', false);
    } catch (error) {
      if (error instanceof BacktestSubmissionError) {
        submitError.value = error.message;
        if (error.code === 'strategy_version_unavailable') await loadCatalog();
      } else {
        submitError.value =
          error instanceof Error ? error.message : 'Batch submission failed.';
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
    if (
      !store.reuseSource &&
      markets.all.length &&
      !draft.value.symbols.length
    ) {
      selectMarket(markets.all[0].symbol_id);
    } else if (!markets.all.length) {
      void markets
        .fetch()
        .then(() => {
          if (
            !store.reuseSource &&
            !draft.value.symbols.length &&
            markets.all.length
          ) {
            selectMarket(markets.all[0].symbol_id);
          }
        })
        .catch(() => {
          fieldErrors.value.market = 'Market options unavailable.';
        });
    }
    void loadCatalog();
  });

  return {
    step,
    navigateStep,
    numericEntryValid,
    hasPendingNumericEntry,
    catalogPending,
    changeParameterMode,
    numericValues,
    setNumericValues,
    store,
    draft,
    sweep,
    isSweep,
    nameIssue,
    catalog,
    catalogError,
    submitError,
    fieldErrors,
    submitting,
    preview,
    previewPending,
    previewError,
    sweepLimit,
    sweepAcceptanceEnabled,
    previewFilter,
    selectedStrategy,
    strategyNeedsReview,
    missingMarkets,
    parameterIssues,
    parameterChanges,
    strategyOptions,
    loadCatalog,
    selectStrategy,
    useCurrentVersion,
    submit,
    submitSweep,
    ...fields,
  };
}
