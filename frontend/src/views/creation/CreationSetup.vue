<template>
  <div class="setup-fields">
    <label
      >Experiment name (optional)
      <n-input
        v-model:value="draft.name"
        data-testid="creation-name"
        placeholder="Enter an experiment name"
        :status="nameIssue ? 'error' : undefined"
      />
    </label>
    <p
      v-if="nameIssue"
      role="alert"
      >{{ nameIssue }}</p
    >
    <label
      >Run type
      <BaseSelect
        :value="isSweep ? 'sweep' : 'standalone'"
        :options="runTypeOptions"
        data-testid="creation-run-type"
        @update:value="setRunType"
      />
    </label>
    <label>
      <span class="strategy-label"
        >Strategy
        <n-tag
          v-if="selectedStrategy"
          size="small"
          round
          :bordered="false"
        >
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
      <n-button
        size="small"
        @click="useCurrentVersion"
        >Use current version</n-button
      >
    </p>
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
            {{ missingMarkets.join(', ') }} unavailable. Remove or replace
            before preview/submission.
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
    <label
      >Initial capital
      <n-input-number
        v-model:value="draft.initial_capital"
        :min="0.01"
        data-testid="creation-capital"
      />
    </label>
    <small
      v-if="fieldErrors.capital"
      role="alert"
      >{{ fieldErrors.capital }}</small
    >
    <CreationExecution />
  </div>
</template>
<script setup lang="ts">
import { NInput, NInputNumber, NTag, NButton } from 'naive-ui';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import BaseDateRange from '@/components/Common/BaseDateRange.vue';
import CreationExecution from './CreationExecution.vue';
import { dateValue } from './creationParameters';
import { runTypeOptions, timeframeOptions } from './creationOptions';
import { useCreation } from './creationContext';
const {
  draft,
  nameIssue,
  isSweep,
  setRunType,
  selectedStrategy,
  strategyOptions,
  selectStrategy,
  store,
  strategyNeedsReview,
  useCurrentVersion,
  marketValue,
  marketOptions,
  selectMarket,
  sweep,
  missingMarkets,
  fieldErrors,
  setDate,
} = useCreation();
</script>
