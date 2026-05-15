<template>
  <base-modal
    :modalId="modalId"
    :title="indicatorInfo.name || 'Indicator Settings'"
    closeOnBackdrop
  >
    <div>
      <div id="indicator-tab-wrapper">
        <n-tabs type="line" animated :tabs-padding="16">
          <n-tab-pane name="settings" tab="Settings">
            <indicator-settings-parameters :indicator="indicator" />
          </n-tab-pane>
          <n-tab-pane name="style" tab="Style">
            <indicator-settings-styles
              :indicatorInfo="indicatorInfo"
              @update-styles="onUpdateStyles"
            />
          </n-tab-pane>
        </n-tabs>
      </div>
    </div>
  </base-modal>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { NTabs, NTabPane } from "naive-ui";

import BaseModal from "@/components/Common/BaseModal.vue";
import IndicatorSettingsParameters from "@/components/Chart/Indicator/IndicatorSettingsParameters.vue";
import IndicatorSettingsStyles from "@/components/Chart/Indicator/IndicatorSettingsStyles.vue";

import type { IndicatorInstance, IndicatorStyleUpdatePayload } from "./types";

defineOptions({
  name: "IndicatorSettingsModal",
});

const props = defineProps<{
  indicator: IndicatorInstance;
  modalId: string;
}>();

const emit = defineEmits<{
  "update-styles": [payload: IndicatorStyleUpdatePayload];
}>();

const indicatorInfo = computed(() => props.indicator.info);

function onUpdateStyles(payload: IndicatorStyleUpdatePayload): void {
  emit("update-styles", payload);
}
</script>
