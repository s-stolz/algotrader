import { useCreationNavigation } from './useCreationNavigation';
import { initialScheduleDraft } from '@/types/backtest/schedule';
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue';
import type { SelectOption } from 'naive-ui';
import {
  BacktestSubmissionError,
  fetchStrategyCatalog,
  fetchBacktestCapabilities,
  previewBacktest,
  submitBacktest,
} from '@/api/backtesterClient';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { useMarketsStore } from '@/stores/marketsStore';
import { normalizeExperimentName } from '@/types/backtesterContracts';
import type {
  BacktestRequestPayload,
  StrategyCatalogEntry,
  BacktestSelectionsDraft,
  BacktestPreview,
  BacktestPreviewRequest,
} from '@/types/backtesterContracts';
import type { ReuseSource } from '../backtestReuse';
import { creationFields } from './creationFields';
import {
  experimentNameIssue,
  parameterIssue,
  parameterModeOptions,
  defaults,
} from './creationParameters';
import {
  initialDraft,
  buildBacktestRequest as createBacktestRequest,
  type DraftRequest,
} from './creationRequest';
import { parameterChanges as describeParameterChanges } from './creationStrategyReview';

export interface CreationEvents {
  (event: 'submitted', backtestId: string): void;
  (event: 'update:show', show: boolean): void;
}
export function useBacktestCreation(emit: CreationEvents) {
  const store = useBacktestWorkspaceStore();
  const markets = useMarketsStore();
  const draft = ref<DraftRequest>(
    (store.creationDraft as DraftRequest | null) ?? initialDraft(),
  );
  const selections = ref<BacktestSelectionsDraft>(
    store.creationSelections ?? {
      marketIds: [],
      timeframes: ['M1'],
      allowedDirections: ['long_and_short'],
      parameters: {},
      dailySchedule: initialScheduleDraft(),
    },
  );
  const nameIssue = computed(() => experimentNameIssue(draft.value.name));
  const scheduleDraft = computed(() => selections.value.dailySchedule);
  const catalog = shallowRef<StrategyCatalogEntry[]>([]);
  const catalogPending = ref(false);
  const catalogError = ref<string | null>(null);
  const submitError = ref<string | null>(null);
  const fieldErrors = ref<Record<string, string>>({});
  const submitting = ref(false);
  const preview = shallowRef<BacktestPreview | null>(null);
  const previewPending = ref(false);
  const previewError = ref<string | null>(null);
  const candidateLimit = ref<number | null>(null);
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
    selections.value.marketIds
      .filter((id) => !markets.all.some((market) => market.symbol_id === id))
      .map((id) => `ID ${id}`),
  );
  const parameterIssues = computed(() => {
    const selected = selectedStrategy.value;
    if (!selected) return [];
    return selected.parameters.flatMap((parameter) => {
      const axis = selections.value.parameters[parameter.name];
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
  const fields = creationFields(draft, selections, fieldErrors, markets);
  const { parameterInput, stringValues, selectMarket } = fields;
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
    setupErrors,
    setupAttempted,
    touchSetup,
    setupFocusRequest,
    resetSetupValidation,
  } = useCreationNavigation({
    draft,
    selections,
    strategyNeedsReview,
    missingMarkets,
    selectedStrategy,
    fieldErrors,
    submitError,
    parameterInput,
    buildBacktestRequest,
  });
  function buildBacktestRequest() {
    return createBacktestRequest(
      draft.value,
      selections.value,
      selectedStrategy.value,
      missingMarkets.value,
      parameterInput,
      stringValues,
    );
  }

  watch(
    draft,
    (value) => {
      store.creationDraft = JSON.parse(
        JSON.stringify(value),
      ) as BacktestRequestPayload;
    },
    { deep: true, immediate: true },
  );
  watch(
    selections,
    (value) => {
      store.creationSelections = JSON.parse(
        JSON.stringify(value),
      ) as BacktestSelectionsDraft;
    },
    { deep: true, immediate: true },
  );

  watch(
    () => store.reuseRevision,
    () => {
      draft.value = store.creationDraft
        ? (JSON.parse(JSON.stringify(store.creationDraft)) as DraftRequest)
        : initialDraft();
      selections.value = store.creationSelections
        ? (JSON.parse(
            JSON.stringify(store.creationSelections),
          ) as BacktestSelectionsDraft)
        : {
            marketIds: [],
            timeframes: ['M1'],
            allowedDirections: ['long_and_short'],
            parameters: {},
            dailySchedule: initialScheduleDraft(),
          };
      if (store.reuseSource && strategyNeedsReview.value) useCurrentVersion();
      step.value = 0;
      resetSetupValidation();
      numericEntryValid.value = {};
      fieldErrors.value = {};
      submitError.value = null;
      submissionId = globalThis.crypto.randomUUID();
      if (
        !selections.value.marketIds.length &&
        !store.reuseSource &&
        markets.all.length
      ) {
        selectMarket(markets.all[0].symbol_id);
      }
    },
  );

  onMounted(() => {
    void fetchBacktestCapabilities()
      .then((capabilities) => {
        candidateLimit.value = capabilities.max_backtest_candidate_count;
      })
      .catch(() => {
        candidateLimit.value = null;
      });
  });

  watch(
    [draft, selections, catalog, () => markets.all],
    () => {
      previewRevision += 1;
      submissionId = globalThis.crypto.randomUUID();
      if (previewTimer) clearTimeout(previewTimer);
      preview.value = null;
      previewPending.value = false;
      previewError.value = null;
      if (!selectedStrategy.value) return;
      let request: BacktestPreviewRequest;
      try {
        request = buildBacktestRequest();
      } catch (error) {
        previewError.value =
          error instanceof Error
            ? error.message
            : 'Complete the backtest inputs.';
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
    request: BacktestPreviewRequest,
    revision: number,
  ): Promise<void> {
    try {
      const result = await previewBacktest(request);
      if (revision !== previewRevision) return;
      preview.value = result;
      candidateLimit.value = result.max_backtest_candidate_count;
    } catch (error) {
      if (revision !== previewRevision) return;
      previewError.value =
        error instanceof Error ? error.message : 'Backtest preview failed.';
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
    selections.value.parameters = {};
    store.reuseSource = null;
    fieldErrors.value = {};
    numericEntryValid.value = {};
  }

  function useCurrentVersion(): void {
    const selected = selectedStrategy.value;
    if (!selected) return;
    const retained = Object.fromEntries(
      selected.parameters
        .filter((parameter) =>
          Object.hasOwn(draft.value.strategy.parameters, parameter.name),
        )
        .map((parameter) => [
          parameter.name,
          draft.value.strategy.parameters[parameter.name],
        ]),
    );
    draft.value.strategy = {
      strategy_id: selected.strategy_id,
      strategy_version: selected.strategy_version,
      parameters: { ...defaults(selected), ...retained },
    };
    submitError.value = null;
  }

  async function submit(): Promise<void> {
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
      const request = buildBacktestRequest();
      const backtestId = await submitBacktest(
        request,
        submissionId,
        normalizeExperimentName(draft.value.name),
      );
      emit('submitted', backtestId);
      emit('update:show', false);
    } catch (error) {
      if (error instanceof BacktestSubmissionError) {
        submitError.value = error.message;
        if (error.code === 'strategy_version_unavailable') await loadCatalog();
      } else {
        submitError.value =
          error instanceof Error
            ? error.message
            : 'Backtest submission failed.';
      }
      const revision = ++previewRevision;
      preview.value = null;
      previewPending.value = true;
      try {
        await refreshPreview(buildBacktestRequest(), revision);
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
      !selections.value.marketIds.length
    ) {
      selectMarket(markets.all[0].symbol_id);
    } else if (!markets.all.length) {
      void markets.fetch().then(() => {
        if (
          !store.reuseSource &&
          !selections.value.marketIds.length &&
          markets.all.length
        ) {
          selectMarket(markets.all[0].symbol_id);
        }
      });
    }
    void loadCatalog();
  });

  return {
    scheduleDraft,
    setupErrors,
    setupAttempted,
    touchSetup,
    setupFocusRequest,
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
    selections,
    nameIssue,
    catalog,
    catalogError,
    submitError,
    fieldErrors,
    submitting,
    preview,
    previewPending,
    previewError,
    candidateLimit,
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
    ...fields,
  };
}
