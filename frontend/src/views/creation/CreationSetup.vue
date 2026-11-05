<template>
  <div
    ref="setupElement"
    class="setup-fields"
  >
    <div
      v-if="setupAttempted && Object.keys(setupErrors).length"
      role="alert"
      class="setup-error-summary"
    >
      Complete the highlighted fields to continue.
    </div>
    <section
      class="setup-section"
      aria-labelledby="setup-experiment"
    >
      <header><span>01</span><h3 id="setup-experiment">Experiment</h3></header>
      <label data-setup-field="name"
        ><span>Experiment name <small>(Optional)</small></span>
        <n-input
          v-model:value="draft.name"
          data-testid="creation-name"
          placeholder="Enter an experiment name"
          :status="nameIssue ? 'error' : undefined"
          :input-props="{
            'aria-label': 'Experiment name',
            'aria-invalid': !!nameIssue,
            'aria-describedby': nameIssue ? 'creation-name-error' : undefined,
          }"
        />
      </label>
      <p
        v-if="nameIssue"
        id="creation-name-error"
        role="alert"
        >{{ nameIssue }}</p
      >
      <div
        class="strategy-field"
        data-setup-field="strategy"
      >
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
          :status="setupErrors.strategy ? 'error' : undefined"
          :options="strategyOptions"
          data-testid="creation-strategy"
          @update:value="selectStrategy"
        />
      </div>
      <small
        v-if="setupErrors.strategy"
        role="alert"
        >{{ setupErrors.strategy }}</small
      >
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
    </section>
    <section
      class="setup-section"
      aria-labelledby="setup-coverage"
    >
      <header
        ><span>02</span
        ><h3 id="setup-coverage">Markets &amp; period</h3></header
      >
      <CreationMarketPeriod />
    </section>
    <section
      class="setup-section"
      aria-labelledby="setup-trading"
    >
      <header><span>03</span><h3 id="setup-trading">Trading rules</h3></header>
      <CreationTradingRules />
    </section>
    <section
      class="setup-section"
      aria-labelledby="setup-schedules"
    >
      <header
        ><span>04</span><h3 id="setup-schedules">Daily schedules</h3></header
      >
      <BacktestScheduleFields
        :schedule="scheduleDraft"
        :errors="setupErrors"
        @change="touchSetup"
      />
    </section>
    <section
      class="setup-section"
      aria-labelledby="setup-execution"
    >
      <header><span>05</span><h3 id="setup-execution">Execution</h3></header>
      <CreationExecution />
    </section>
  </div>
</template>
<script setup lang="ts">
import CreationStrategyReview from './CreationStrategyReview.vue';
import { nextTick, ref, watch } from 'vue';
import { NInput, NTag, NButton } from 'naive-ui';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import CreationMarketPeriod from './CreationMarketPeriod.vue';
import CreationExecution from './CreationExecution.vue';
import CreationTradingRules from './setup/CreationTradingRules.vue';
import BacktestScheduleFields from '../BacktestScheduleFields.vue';
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
  scheduleDraft,
  setupErrors,
  setupAttempted,
  setupFocusRequest,
  touchSetup,
} = useCreation();
const setupElement = ref<HTMLElement>();
watch(setupFocusRequest, async () => {
  await nextTick();
  const key = Object.keys(setupErrors.value)[0];
  const field = setupElement.value?.querySelector<HTMLElement>(
    `[data-setup-field="${key}"]`,
  );
  field?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' });
  (
    field?.querySelector<HTMLElement>(
      'input:not([type="hidden"]):not(:disabled)',
    ) ?? field?.querySelector<HTMLElement>('[tabindex="0"], button')
  )?.focus({ preventScroll: true });
});
</script>
<style scoped>
.setup-section {
  display: grid;
  gap: 18px;
  padding-bottom: 26px;
  margin-bottom: 8px;
  border-bottom: 1px solid var(--design-color-border);
}
header {
  display: flex;
  gap: 10px;
  align-items: center;
}
header > span {
  color: var(--design-color-interactive);
  font-size: 11px;
}
h3 {
  font-size: 15px;
  font-weight: 550;
  margin: 0;
}
.setup-error-summary {
  border-left: 3px solid var(--design-color-error);
  padding: 12px 16px;
  background: var(--design-color-inset);
}
</style>
