<template>
  <section
    class="market-period"
    aria-label="Market and period"
  >
    <div class="settings-grid">
      <div class="field-group">
        <label v-if="!isSweep"
          >Market
          <BaseSelect
            :value="marketValue"
            :options="marketOptions"
            data-testid="creation-market"
            @update:value="selectMarket"
          />
        </label>
        <label v-else
          >Markets
          <BaseSelect
            v-model:value="sweep.marketIds"
            multiple
            max-tag-count="responsive"
            :options="marketOptions"
            data-testid="sweep-markets"
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
          v-if="fieldErrors.market"
          role="alert"
          >{{ fieldErrors.market }}</small
        >
      </div>
      <div class="field-group">
        <label v-if="!isSweep"
          >Timeframe
          <BaseSelect
            v-model:value="draft.timeframe"
            :options="timeframeOptions"
            data-testid="creation-timeframe"
          />
        </label>
        <label v-else
          >Timeframes
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
      <small
        v-if="fieldErrors.dates"
        class="full-width"
        role="alert"
        >{{ fieldErrors.dates }}</small
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
  isSweep,
  marketValue,
  marketOptions,
  selectMarket,
  sweep,
  missingMarkets,
  fieldErrors,
  setDate,
} = useCreation();
</script>
