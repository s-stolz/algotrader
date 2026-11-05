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
    <div class="strategy-field">
      <span
        id="creation-strategy-label"
        class="strategy-label"
        >Strategy
        <n-tag
          v-if="selectedStrategy"
          size="small"
          round
          :bordered="false"
        >
          Version {{ selectedStrategy.strategy_version }}
        </n-tag>
        <CreationStrategyReview />
      </span>
      <BaseSelect
        :input-props="{ 'aria-labelledby': 'creation-strategy-label' }"
        :value="draft.strategy.strategy_id"
        :options="strategyOptions"
        data-testid="creation-strategy"
        @update:value="selectStrategy"
      />
    </div>
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
    <CreationMarketPeriod />
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
import CreationStrategyReview from './CreationStrategyReview.vue';
import { NInput, NInputNumber, NTag, NButton } from 'naive-ui';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import CreationMarketPeriod from './CreationMarketPeriod.vue';
import CreationExecution from './CreationExecution.vue';
import { useCreation } from './creationContext';
const {
  draft,
  nameIssue,
  selectedStrategy,
  strategyOptions,
  selectStrategy,
  store,
  strategyNeedsReview,
  useCurrentVersion,
  fieldErrors,
} = useCreation();
</script>
