<template>
  <section
    class="settings-section"
    aria-labelledby="market-period-heading"
  >
    <h3 id="market-period-heading">Market &amp; period</h3>
    <p class="section-description"
      >Choose the historical data for your backtest. Dates use UTC.</p
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
            :options="timeframeOptions"
            data-testid="sweep-timeframes"
          />
        </label>
      </div>
      <label
        >Start date (UTC)
        <BaseDatePicker
          type="date"
          value-format="yyyy-MM-dd"
          :formatted-value="dateValue(draft.start_ms)"
          :clearable="false"
          :input-readonly="true"
          data-testid="creation-start"
          @update:formatted-value="setDate('start_ms', $event)"
        />
      </label>
      <label
        >End date (UTC)
        <BaseDatePicker
          type="date"
          value-format="yyyy-MM-dd"
          :formatted-value="dateValue(draft.end_ms)"
          :clearable="false"
          :input-readonly="true"
          data-testid="creation-end"
          @update:formatted-value="setDate('end_ms', $event)"
        />
      </label>
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
import BaseSelect from '@/components/Common/BaseSelect.vue';
import BaseDatePicker from '@/components/Common/BaseDatePicker.vue';
import { timeframeOptions } from './creationOptions';
import { dateValue } from './creationParameters';
import { useCreation } from './creationContext';
const {
  isSweep,
  draft,
  sweep,
  marketValue,
  marketOptions,
  missingMarkets,
  fieldErrors,
  selectMarket,
  setDate,
} = useCreation();
</script>
