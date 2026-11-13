<template>
  <BaseStepModal
    class="backtest-creation"
    :show="show"
    title="Create Backtest"
    :steps="['Setup', 'Parameters', 'Review']"
    :step="step"
    :fill-body="step === 2"
    @update:step="navigateStep"
    @update:show="emit('update:show', $event)"
  >
    <BaseAsyncState
      v-if="catalogPending || catalogError"
      :kind="catalogPending ? 'loading' : 'error'"
      label="Strategy catalog"
      :message="
        catalog.length
          ? 'Couldn’t refresh strategies.'
          : 'Strategies unavailable.'
      "
      :retry="!!catalogError"
      @retry="loadCatalog"
    />
    <template
      v-if="draft && catalog.length && !catalogPending && !catalogError"
    >
      <p
        v-if="
          store.reuseSource &&
          !selectedStrategy &&
          draft.strategy.strategy_id === store.reuseSource.strategyId
        "
        role="alert"
        data-testid="reuse-removed-strategy"
      >
        Strategy {{ store.reuseSource.strategyId }} is no longer registered.
        This saved record remains inspectable. Choose a current strategy to
        create new work.
      </p>
      <div
        v-show="step !== 2"
        class="creation-fields"
      >
        <CreationSetup v-show="step === 0" />
        <CreationParameters v-show="step === 1" />
      </div>
      <BaseAsyncState
        v-if="submitError && !submitting"
        kind="error"
        compact
        label="Submission failed"
        message="Couldn’t create this backtest."
        :retry="!previewPending && !previewError && !!preview?.ready_count"
        @retry="submit"
      />
      <CreationReview v-show="step === 2" />
    </template>
    <template #footer>
      <div
        v-if="!catalogPending && !catalogError"
        class="creation-footer"
      >
        <n-tag
          round
          :bordered="false"
          :type="!preview?.ready_count ? 'warning' : 'success'"
        >
          {{ preview?.raw_count ?? 0 }} candidates
        </n-tag>
        <div class="creation-actions">
          <n-button
            v-if="step > 0"
            @click="navigateStep(step - 1)"
            >Back</n-button
          >
          <n-button
            v-if="step < 2"
            type="primary"
            @click="navigateStep(step + 1)"
          >
            {{ step === 0 ? 'Parameters →' : 'Review candidates →' }}
          </n-button>
          <div v-show="step === 2">
            <n-button
              type="primary"
              :disabled="
                !!nameIssue ||
                submitting ||
                previewPending ||
                !preview ||
                !!previewError ||
                strategyNeedsReview ||
                parameterIssues.length > 0 ||
                missingMarkets.length > 0 ||
                !preview.ready_count ||
                hasPendingNumericEntry
              "
              :loading="submitting"
              data-testid="creation-submit"
              @click="submit"
              >Create Backtest</n-button
            >
          </div></div
        ></div
      >
    </template>
  </BaseStepModal>
</template>

<script setup lang="ts">
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';

import { provide } from 'vue';
import { NButton, NTag } from 'naive-ui';
import BaseStepModal from '@/components/Common/BaseStepModal.vue';
import CreationSetup from '@/views/creation/CreationSetup.vue';
import CreationParameters from '@/views/creation/CreationParameters.vue';
import CreationReview from '@/views/creation/CreationReview.vue';
import { creationKey } from '@/views/creation/creationContext';
import { useBacktestCreation } from '@/views/creation/useBacktestCreation';
defineProps<{ show: boolean }>();
const emit = defineEmits<{
  'update:show': [show: boolean];
  submitted: [backtestId: string];
}>();
const creation = useBacktestCreation(emit);
provide(creationKey, creation);
const {
  step,
  navigateStep,
  catalogPending,
  catalogError,
  loadCatalog,
  draft,
  catalog,
  store,
  selectedStrategy,
  strategyNeedsReview,
  submitError,
  preview,
  submitting,
  nameIssue,
  submit,
  previewPending,
  previewError,
  parameterIssues,
  missingMarkets,
  hasPendingNumericEntry,
} = creation;
</script>
<style scoped src="@/views/creation/creation.css"></style>
