import { dailyEntryLimitIssue } from '@/types/backtest/entryLimit';
import { dailyScheduleIssue } from '@/types/backtest/schedule';
import { computed, ref, type Ref } from 'vue';
import type {
  StrategyCatalogEntry,
  StrategyParameterSchema,
  BacktestSelectionsDraft,
  ParameterDraft,
  BacktestPreviewRequest,
} from '@/types/backtesterContracts';
import type { DraftRequest } from './creationRequest';
import { parameterIssue } from './creationParameters';
interface NavigationInputs {
  draft: Ref<DraftRequest>;
  selections: Ref<BacktestSelectionsDraft>;
  nameIssue: Ref<string | null>;
  strategyNeedsReview: Ref<boolean>;
  missingMarkets: Ref<string[]>;
  selectedStrategy: Ref<StrategyCatalogEntry | undefined>;
  fieldErrors: Ref<Record<string, string>>;
  submitError: Ref<string | null>;
  parameterInput: (parameter: StrategyParameterSchema) => ParameterDraft;
  buildBacktestRequest: () => BacktestPreviewRequest;
}
export function useCreationNavigation(inputs: NavigationInputs) {
  const {
    draft,
    selections,
    nameIssue,
    strategyNeedsReview,
    missingMarkets,
    selectedStrategy,
    fieldErrors,
    submitError,
    parameterInput,
    buildBacktestRequest,
  } = inputs;
  const step = ref(0);
  const numericEntryValid = ref<Record<string, boolean>>({});
  function navigateStep(next: number): void {
    if (next > step.value) {
      fieldErrors.value = {};
      if (!validateSetup()) {
        step.value = 0;
        return;
      }
      if (next === 2 && !validateParameters()) {
        step.value = 1;
        return;
      }
    }
    step.value = next;
  }
  function validateSetup(): boolean {
    if (nameIssue.value) fieldErrors.value.name = nameIssue.value;
    if (strategyNeedsReview.value)
      fieldErrors.value.strategy = 'Review the current Strategy Version.';
    if (!selections.value.marketIds.length || missingMarkets.value.length) {
      fieldErrors.value.market = 'Select an available Market.';
    }
    if (!selections.value.timeframes.length)
      fieldErrors.value.timeframe = 'Select at least one Timeframe.';
    if (
      !Number.isFinite(draft.value.start_ms) ||
      !Number.isFinite(draft.value.end_ms) ||
      draft.value.start_ms <= 0 ||
      draft.value.end_ms <= draft.value.start_ms
    ) {
      fieldErrors.value.dates = 'End date must be after start date.';
    }
    if (
      !Number.isFinite(draft.value.initial_capital) ||
      draft.value.initial_capital <= 0
    ) {
      fieldErrors.value.capital = 'Initial capital must be greater than zero.';
    }
    return !Object.keys(fieldErrors.value).length;
  }
  function validateParameters(): boolean {
    const executionIssue =
      dailyScheduleIssue(draft.value.execution.daily_schedule) ??
      dailyEntryLimitIssue(draft.value.execution.max_entries_per_day);
    if (executionIssue) {
      submitError.value = executionIssue;
      return false;
    }
    {
      try {
        buildBacktestRequest();
      } catch (error) {
        submitError.value =
          error instanceof Error ? error.message : 'Complete parameter values.';
        return false;
      }
      if (hasPendingNumericEntry.value) {
        submitError.value = 'Finish adding or clear the numeric value.';
        return false;
      }
    }
    for (const parameter of selectedStrategy.value?.parameters ?? []) {
      if (parameterInput(parameter).mode !== 'constant') continue;
      const issue = parameterIssue(
        parameter,
        draft.value.strategy.parameters[parameter.name],
      );
      if (issue) fieldErrors.value[parameter.name] = issue;
    }
    return !Object.keys(fieldErrors.value).length;
  }

  const hasPendingNumericEntry = computed(() =>
    Object.entries(numericEntryValid.value).some(
      ([name, valid]) =>
        !valid && selections.value.parameters[name]?.mode === 'values',
    ),
  );

  function changeParameterMode(
    parameter: StrategyParameterSchema,
    mode: ParameterDraft['mode'],
  ): void {
    parameterInput(parameter).mode = mode;
    numericEntryValid.value[parameter.name] = true;
    if (
      mode === 'constant' &&
      (parameter.type === 'int' || parameter.type === 'float') &&
      !parameter.choices
    ) {
      delete draft.value.strategy.parameters[parameter.name];
    }
  }

  function numericValues(parameter: StrategyParameterSchema): number[] {
    return parameterInput(parameter)
      .valuesText.split('\n')
      .filter(Boolean)
      .map(Number);
  }

  function setNumericValues(
    parameter: StrategyParameterSchema,
    values: number[],
  ): void {
    parameterInput(parameter).valuesText = values.map(String).join('\n');
    delete parameterInput(parameter).selectedChoiceValues;
  }

  return {
    step,
    navigateStep,
    numericEntryValid,
    hasPendingNumericEntry,
    changeParameterMode,
    numericValues,
    setNumericValues,
    validateSetup,
    validateParameters,
  };
}
