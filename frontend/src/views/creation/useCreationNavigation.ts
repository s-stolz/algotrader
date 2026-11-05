import { computed, ref, type Ref } from 'vue';
import { setupIssues } from './setup/setupValidation';
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
    strategyNeedsReview,
    missingMarkets,
    selectedStrategy,
    fieldErrors,
    submitError,
    parameterInput,
    buildBacktestRequest,
  } = inputs;
  const step = ref(0);
  const setupAttempted = ref(false);
  const touchedSetup = ref<Record<string, boolean>>({});
  const setupFocusRequest = ref(0);
  const setupValidation = computed(() =>
    setupIssues(
      draft.value,
      selections.value,
      strategyNeedsReview.value,
      missingMarkets.value,
    ),
  );
  const setupErrors = computed(() =>
    Object.fromEntries(
      Object.entries(setupValidation.value).filter(
        ([key]) => setupAttempted.value || touchedSetup.value[key],
      ),
    ),
  );
  function touchSetup(field: string) {
    touchedSetup.value[field] = true;
  }
  function resetSetupValidation() {
    setupAttempted.value = false;
    touchedSetup.value = {};
  }
  const numericEntryValid = ref<Record<string, boolean>>({});
  function navigateStep(next: number): void {
    if (next > step.value) {
      fieldErrors.value = {};
      if (!validateSetup()) {
        step.value = 0;
        setupFocusRequest.value += 1;
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
    setupAttempted.value = true;
    return !Object.keys(setupValidation.value).length;
  }
  function validateParameters(): boolean {
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
    setupErrors,
    setupAttempted,
    setupValidation,
    touchSetup,
    setupFocusRequest,
    resetSetupValidation,
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
