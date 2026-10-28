<template>
  <p
    v-if="store.reuseSource"
    data-testid="reuse-source"
  >
    Editing a new
    {{ store.reuseSource.kind === 'run' ? 'Backtest' : 'Parameter Sweep' }}
    from saved {{ store.reuseSource.kind }}
    <span class="technical-id">{{ store.reuseSource.id }}</span
    >. The saved history stays unchanged.
  </p>
  <p
    v-if="
      store.reuseSource &&
      !selectedStrategy &&
      draft.strategy.strategy_id === store.reuseSource.strategyId
    "
    role="alert"
    data-testid="reuse-removed-strategy"
  >
    Strategy {{ store.reuseSource.strategyId }} is no longer registered. This
    saved record remains inspectable. Choose a current strategy to create new
    work.
  </p>
  <p
    v-if="store.reuseSource && selectedStrategy && strategyNeedsReview"
    role="alert"
    data-testid="reuse-version-review"
  >
    Saved {{ store.reuseSource.strategyId }} version
    {{ store.reuseSource.strategyVersion ?? 'unavailable (legacy request)' }};
    current version {{ selectedStrategy.strategy_version }}. Review parameter
    changes and invalid values before submitting. This is a new experiment, not
    an exact reproduction.
    <n-button
      size="small"
      data-testid="reuse-use-current"
      @click="useCurrentVersion"
    >
      Use current version
    </n-button>
  </p>
  <p
    v-for="change in parameterChanges"
    :key="change"
    role="status"
    >{{ change }}</p
  >
  <div class="creation-fields">
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
    <slot
  /></div>
</template>

<script setup lang="ts">
import BaseSelect from '@/components/Common/BaseSelect.vue';
import { NButton, NInput, NTag } from 'naive-ui';
import { runTypeOptions } from './creationOptions';
import { useCreation } from './creationContext';
const {
  store,
  draft,
  nameIssue,
  isSweep,
  selectedStrategy,
  strategyNeedsReview,
  parameterChanges,
  setRunType,
  selectStrategy,
  useCurrentVersion,
  strategyOptions,
} = useCreation();
</script>
