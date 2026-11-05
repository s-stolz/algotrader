<template>
  <section
    class="market-period"
    aria-label="Market and period"
  >
    <div class="settings-grid">
      <div
        class="field-group"
        data-setup-field="market"
      >
        <label
          >Markets
          <BaseSelect
            v-model:value="selections.marketIds"
            multiple
            filterable
            clearable
            max-tag-count="responsive"
            :options="marketOptions"
            data-testid="selections-markets"
            :status="setupErrors.market ? 'error' : undefined"
            :input-props="{
              'aria-label': 'Markets',
              'aria-invalid': !!setupErrors.market,
              'aria-describedby': setupErrors.market
                ? 'creation-markets-error'
                : undefined,
            }"
            @update:value="touchSetup('market')"
          />
        </label>
        <small
          v-if="!marketOptions.length"
          role="alert"
          >Market options unavailable.</small
        >
        <small
          v-if="missingMarkets.length"
          role="alert"
          data-testid="reuse-missing-market"
        >
          Saved Market{{ missingMarkets.length === 1 ? '' : 's' }}
          {{ missingMarkets.join(', ') }} unavailable. Remove or replace before
          preview/submission.
        </small>
        <small
          v-if="setupErrors.market"
          id="creation-markets-error"
          role="alert"
          >{{ setupErrors.market }}</small
        >
      </div>
      <div
        class="field-group"
        data-setup-field="timeframe"
      >
        <label
          >Timeframes
          <BaseSelect
            v-model:value="selections.timeframes"
            multiple
            filterable
            clearable
            max-tag-count="responsive"
            :options="timeframeOptions"
            data-testid="selections-timeframes"
            :status="setupErrors.timeframe ? 'error' : undefined"
            :input-props="{
              'aria-label': 'Timeframes',
              'aria-invalid': !!setupErrors.timeframe,
              'aria-describedby': setupErrors.timeframe
                ? 'creation-timeframes-error'
                : undefined,
            }"
            @update:value="touchSetup('timeframe')"
          />
        </label>
        <small
          v-if="setupErrors.timeframe"
          id="creation-timeframes-error"
          role="alert"
          >{{ setupErrors.timeframe }}</small
        >
      </div>
      <BaseDateRange
        class="full-width"
        data-setup-field="dates"
        :invalid="!!setupErrors.dates"
        error-id="creation-dates-error"
        :start="dateValue(draft.start_ms)"
        :end="dateValue(draft.end_ms)"
        @update:start="
          setDate('start_ms', $event);
          touchSetup('dates');
        "
        @update:end="
          setDate('end_ms', $event);
          touchSetup('dates');
        "
      />
      <small
        v-if="setupErrors.dates"
        id="creation-dates-error"
        class="full-width"
        role="alert"
        >{{ setupErrors.dates }}</small
      >
    </div>
  </section>
</template>
<script setup lang="ts">
import BaseDateRange from '@/components/Common/BaseDateRange.vue';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import { dateValue } from './creationParameters';
import { timeframeOptions } from './creationOptions';
import { useCreation } from './creationContext';
const {
  draft,
  marketOptions,
  selections,
  missingMarkets,
  setupErrors,
  touchSetup,
  setDate,
} = useCreation();
</script>
