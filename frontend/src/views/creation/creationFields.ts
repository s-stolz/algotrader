import { computed, type Ref } from 'vue';
import type { SelectOption } from 'naive-ui';
import type {
  StrategyParameterSchema,
  SweepDraftState,
  SweepParameterDraft,
} from '@/types/backtesterContracts';
import type { useMarketsStore } from '@/stores/marketsStore';
import type { DraftRequest } from './creationRequest';
import { choiceValues } from './creationParameters';

export function creationFields(
  draft: Ref<DraftRequest>,
  sweep: Ref<SweepDraftState>,
  fieldErrors: Ref<Record<string, string>>,
  markets: ReturnType<typeof useMarketsStore>,
) {
  const marketOptions = computed<SelectOption[]>(() =>
    markets.all.map((market) => ({
      label: `${market.symbol} · ${market.exchange}`,
      value: market.symbol_id,
    })),
  );
  const marketValue = computed(
    () =>
      markets.all.find(
        (market) =>
          market.symbol === draft.value.symbols[0] &&
          market.exchange === draft.value.exchange,
      )?.symbol_id,
  );
  function sweepParameter(
    parameter: StrategyParameterSchema,
  ): SweepParameterDraft {
    return (sweep.value.parameters[parameter.name] ??= {
      mode: 'constant',
      valuesText: '',
      stringValues: [],
      choiceIndexes: [],
      includeNull: false,
      rangeStart: null,
      rangeStop: null,
      rangeStep: null,
    });
  }

  function stringValues(parameter: StrategyParameterSchema): string[] {
    const input = sweepParameter(parameter);
    return (input.stringValues ??=
      input.valuesText === '' ? [] : input.valuesText.split('\n'));
  }

  function selectedChoiceIndexes(parameter: StrategyParameterSchema): number[] {
    const input = sweepParameter(parameter);
    if (!input.selectedChoiceValues) return input.choiceIndexes;
    return input.selectedChoiceValues
      .map((value) =>
        choiceValues(parameter).findIndex((choice) => choice === value),
      )
      .filter((index) => index >= 0);
  }

  function setSweepChoices(
    parameter: StrategyParameterSchema,
    indexes: number[],
  ): void {
    const input = sweepParameter(parameter);
    input.choiceIndexes = indexes;
    input.selectedChoiceValues = indexes.map(
      (index) => choiceValues(parameter)[index],
    );
  }

  function setRunType(value: string): void {
    sweep.value.isSweep = value === 'sweep';
    if (sweep.value.isSweep) {
      if (!sweep.value.marketIds.length && marketValue.value !== undefined) {
        sweep.value.marketIds = [marketValue.value];
      }
      if (!sweep.value.timeframes.length)
        sweep.value.timeframes = [draft.value.timeframe];
      if (!sweep.value.allowedDirections.length) {
        sweep.value.allowedDirections = [
          draft.value.execution.allowed_directions,
        ];
      }
    }
  }

  function selectValue(parameter: StrategyParameterSchema): number | null {
    const value = draft.value.strategy.parameters[parameter.name];
    const index = choiceValues(parameter).findIndex(
      (choice) => choice === value,
    );
    return index < 0 ? null : index;
  }

  function setChoice(parameter: StrategyParameterSchema, value: number): void {
    setParameter(parameter.name, choiceValues(parameter)[value]);
  }

  function setParameter(name: string, value: unknown): void {
    draft.value.strategy.parameters[name] = value as
      | null
      | boolean
      | number
      | string;
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

  function setDate(field: 'start_ms' | 'end_ms', value: string | null): void {
    draft.value[field] = value ? Date.parse(`${value}T00:00:00Z`) : 0;
    delete fieldErrors.value.dates;
  }
  return {
    marketOptions,
    marketValue,
    sweepParameter,
    stringValues,
    selectedChoiceIndexes,
    setSweepChoices,
    setRunType,
    selectValue,
    setChoice,
    setParameter,
    numberValue,
    stringValue,
    selectMarket,
    setDate,
  };
}
