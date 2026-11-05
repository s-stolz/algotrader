import { computed, type Ref } from 'vue';
import type { SelectOption } from 'naive-ui';
import type {
  StrategyParameterSchema,
  BacktestSelectionsDraft,
  ParameterDraft,
} from '@/types/backtesterContracts';
import type { useMarketsStore } from '@/stores/marketsStore';
import type { DraftRequest } from './creationRequest';
import { choiceValues } from './creationParameters';

export function creationFields(
  draft: Ref<DraftRequest>,
  selections: Ref<BacktestSelectionsDraft>,
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
  function parameterInput(parameter: StrategyParameterSchema): ParameterDraft {
    return (selections.value.parameters[parameter.name] ??= {
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
    const input = parameterInput(parameter);
    return (input.stringValues ??=
      input.valuesText === '' ? [] : input.valuesText.split('\n'));
  }

  function selectedChoiceIndexes(parameter: StrategyParameterSchema): number[] {
    const input = parameterInput(parameter);
    if (!input.selectedChoiceValues) return input.choiceIndexes;
    return input.selectedChoiceValues
      .map((value) =>
        choiceValues(parameter).findIndex((choice) => choice === value),
      )
      .filter((index) => index >= 0);
  }

  function setParameterChoices(
    parameter: StrategyParameterSchema,
    indexes: number[],
  ): void {
    const input = parameterInput(parameter);
    input.choiceIndexes = indexes;
    input.selectedChoiceValues = indexes.map(
      (index) => choiceValues(parameter)[index],
    );
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
    selections.value.marketIds = [symbolId];
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
    parameterInput,
    stringValues,
    selectedChoiceIndexes,
    setParameterChoices,
    selectValue,
    setChoice,
    setParameter,
    numberValue,
    stringValue,
    selectMarket,
    setDate,
  };
}
