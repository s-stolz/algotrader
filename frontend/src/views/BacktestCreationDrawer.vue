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
    <p
      v-if="catalogPending"
      role="status"
      >Loading strategies…</p
    >
    <p
      v-if="catalogError"
      role="alert"
      >Strategy catalog unavailable. {{ catalogError }}</p
    >
    <n-button
      v-if="catalogError"
      @click="loadCatalog"
      >Retry catalog</n-button
    >
    <template v-if="draft && catalog.length">
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
      <p
        v-if="submitError"
        role="alert"
        >{{ submitError }}</p
      >
      <CreationReview v-show="step === 2" />
    </template>
    <template #footer>
      <div class="creation-footer">
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
import { provide } from 'vue';
import { NButton, NTag } from 'naive-ui';
import BaseStepModal from '@/components/Common/BaseStepModal.vue';
import CreationSetup from './creation/CreationSetup.vue';
import CreationParameters from './creation/CreationParameters.vue';
import CreationReview from './creation/CreationReview.vue';
import { creationKey } from './creation/creationContext';
import { useBacktestCreation } from './creation/useBacktestCreation';
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
<style scoped src="./creation/creation.css"></style>
