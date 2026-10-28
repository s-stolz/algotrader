<template>
  <BaseDrawer
    :show="show"
    class="backtest-creation"
    width="min(100vw, max(720px, 66.667vw))"
    @update:show="emit('update:show', $event)"
  >
    <n-drawer-content
      :title="isSweep ? 'Review Parameter Sweep' : 'Create standalone Backtest'"
      closable
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
        <CreationSetup>
          <CreationParameters />
          <CreationMarketPeriod />
          <CreationExecution />
        </CreationSetup>
        <CreationReview />
      </template>
      <template #footer>
        <n-button
          v-if="draft && catalog.length && !isSweep"
          type="primary"
          :disabled="
            submitting ||
            !marketOptions.length ||
            !!catalogError ||
            !selectedStrategy ||
            strategyNeedsReview
          "
          :loading="submitting"
          data-testid="creation-submit"
          @click="submit"
          >Create Backtest</n-button
        >
        <n-button
          v-else-if="isSweep && sweepAcceptanceEnabled"
          type="primary"
          :disabled="
            submitting ||
            previewPending ||
            !preview ||
            !!previewError ||
            strategyNeedsReview ||
            parameterIssues.length > 0 ||
            missingMarkets.length > 0
          "
          :loading="submitting"
          data-testid="sweep-submit"
          @click="submitSweep"
          >Accept Batch</n-button
        >
        <span v-else-if="isSweep"
          >Parameter Sweep submission becomes available with batch
          execution.</span
        >
      </template>
    </n-drawer-content>
  </BaseDrawer>
</template>

<script setup lang="ts">
import { provide } from 'vue';
import BaseDrawer from '@/components/Common/BaseDrawer.vue';
import { NButton, NDrawerContent } from 'naive-ui';
import CreationSetup from './creation/CreationSetup.vue';
import CreationParameters from './creation/CreationParameters.vue';
import CreationMarketPeriod from './creation/CreationMarketPeriod.vue';
import CreationExecution from './creation/CreationExecution.vue';
import CreationReview from './creation/CreationReview.vue';
import { useBacktestCreation } from './creation/useBacktestCreation';
import { creationKey } from './creation/creationContext';

defineProps<{ show: boolean }>();
const emit = defineEmits<{
  'update:show': [show: boolean];
  submitted: [runId: string];
  'submitted-batch': [batchId: string];
}>();
const creation = useBacktestCreation(emit);
provide(creationKey, creation);
const {
  isSweep,
  catalog,
  catalogError,
  draft,
  submitting,
  marketOptions,
  selectedStrategy,
  strategyNeedsReview,
  previewPending,
  preview,
  previewError,
  parameterIssues,
  missingMarkets,
  sweepAcceptanceEnabled,
  loadCatalog,
  submit,
  submitSweep,
} = creation;
</script>

<style scoped src="./creation/creation.css"></style>
