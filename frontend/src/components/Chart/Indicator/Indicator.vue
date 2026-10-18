<template>
  <div>
    <Teleport
      :to="indicator.paneHtmlElement?.querySelector(PANE_OVERLAY_SELECTOR)"
      v-if="indicator.paneHtmlElement"
    >
      <div class="indicator-container">
        <indicator-panel :indicator="indicator" @remove-indicator="onRemoveIndicator" />
      </div>
    </Teleport>

    <indicator-settings-modal
      :indicator="indicator"
      :modalId="`indicatorSettings_${indicator._id}`"
      @update-styles="onUpdateStyles"
    />
  </div>
</template>

<script setup lang="ts">
import { watch } from "vue";

import IndicatorPanel from "./IndicatorPanel.vue";
import IndicatorSettingsModal from "./IndicatorSettingsModal.vue";
import {
  getOrCreatePaneOverlayWrapper,
  PANE_OVERLAY_SELECTOR,
} from "@/utils/chart/paneOverlay";

import type {
  IndicatorInstance,
  IndicatorManagerDependency,
  IndicatorStyleUpdatePayload,
} from "./types";

defineOptions({
  name: "Indicator",
});

const props = defineProps<{
  indicatorManager: IndicatorManagerDependency;
  indicator: IndicatorInstance;
}>();

const emit = defineEmits<{
  "remove-indicator": [indicatorId: string];
}>();

watch(
  () => props.indicator,
  (newValue) => {
    void props.indicatorManager.addIndicatorSeries(newValue._id);
  },
  { immediate: true },
);

watch(
  () => props.indicator.dataVersion,
  () => {
    props.indicatorManager.refreshIndicatorSeries(props.indicator._id);
  },
);

watch(
  () => props.indicator.paneIndex,
  (paneIndex) => {
    if (paneIndex === null || paneIndex === undefined) {
      return;
    }

    void props.indicatorManager.updateMissingPaneHtmlElements();
  },
  { immediate: true },
);

watch(
  () => props.indicator.paneHtmlElement,
  (paneHtmlElement) => {
    if (!paneHtmlElement) {
      return;
    }

    getOrCreatePaneOverlayWrapper(paneHtmlElement);
  },
  { immediate: true },
);

function onRemoveIndicator(indicatorId: string): void {
  props.indicatorManager.removeIndicatorSeriesAndData(indicatorId);
  void props.indicatorManager.updateMissingPaneHtmlElements();
  emit("remove-indicator", indicatorId);
}

function onUpdateStyles({ outputKey, styles }: IndicatorStyleUpdatePayload): void {
  props.indicatorManager.updateIndicatorStyles(props.indicator._id, outputKey, styles);
}

</script>

<style scoped>
.indicator-container {
  margin-bottom: 8px;
}
</style>
