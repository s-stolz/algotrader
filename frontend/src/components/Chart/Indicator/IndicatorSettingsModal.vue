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
            <indicator-settings-styles :indicatorInfo="indicatorInfo" @update-styles="onUpdateStyles" />
          </n-tab-pane>
        </n-tabs>
      </div>
    </div>
  </base-modal>
</template>

<script>
import BaseModal from "@/components/Common/BaseModal.vue";
import IndicatorSettingsParameters from "@/components/Chart/Indicator/IndicatorSettingsParameters.vue";
import IndicatorSettingsStyles from "@/components/Chart/Indicator/IndicatorSettingsStyles.vue";

import { NTabs, NTabPane } from "naive-ui";

export default {
  name: "IndicatorSettingsModal",

  components: {
    BaseModal,
    IndicatorSettingsParameters,
    IndicatorSettingsStyles,
    NTabs,
    NTabPane,
  },

  props: {
    indicator: {
      type: Object,
      required: true,
    },
    modalId: {
      type: String,
      required: true,
    },
  },

  emits: ["update-styles"],

  computed: {
    indicatorInfo() {
      return this.indicator?.info;
    },
  },

  methods: {
    onUpdateStyles({ outputKey, styles }) {
      this.$emit("update-styles", { outputKey, styles });
    },
  },
};
</script>
