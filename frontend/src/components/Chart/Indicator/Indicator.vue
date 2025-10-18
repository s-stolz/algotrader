<template>
  <div>
    <Teleport
      :to="indicator.paneHtmlElement?.querySelector('.indicators-wrapper')"
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

<script>
import IndicatorPanel from "./IndicatorPanel.vue";
import IndicatorSettingsModal from "./IndicatorSettingsModal.vue";

export default {
  name: "Indicator",

  components: {
    IndicatorPanel,
    IndicatorSettingsModal,
  },

  props: {
    indicatorManager: {
      type: Object,
      required: true,
    },

    indicator: {
      type: Object,
      required: true,
    },
  },

  emits: ["remove-indicator"],

  data() {
    return {};
  },

  watch: {
    indicator: {
      handler(newVal, _oldVal) {
        if (!newVal) return;

        this.indicatorManager.addIndicatorSeries(newVal._id);
      },
      immediate: true,
    },

    "indicator.data": {
      handler() {
        if (!this.indicator || !this.indicator._id) return;

        this.indicatorManager.refreshIndicatorSeries(this.indicator._id);
      },
    },

    "indicator.paneIndex": {
      handler(paneIndex) {
        if (paneIndex === null || paneIndex === undefined) {
          return;
        }

        this.indicatorManager.updateMissingPaneHtmlElements();
      },
      immediate: true,
    },

    "indicator.paneHtmlElement": {
      handler(paneHtmlElement) {
        if (!paneHtmlElement) {
          return;
        }

        paneHtmlElement.style.position = "relative";

        if (!paneHtmlElement.querySelector(".indicators-wrapper")) {
          const wrapper = this.createNewIndicatorsWrapper();
          paneHtmlElement.appendChild(wrapper);
        }
      },
      immediate: true,
    },
  },

  methods: {
    onRemoveIndicator(indicatorId) {
      this.indicatorManager.removeIndicatorSeriesAndData(indicatorId);
      this.indicatorManager.updateMissingPaneHtmlElements();
    },

    onUpdateStyles({ outputKey, styles }) {
      this.indicatorManager.updateIndicatorStyles(this.indicator._id, outputKey, styles);
    },

    createNewIndicatorsWrapper() {
      const wrapper = document.createElement("div");
      wrapper.className = "indicators-wrapper";
      wrapper.style.cssText = `
        position: absolute;
        top: 10px;
        left: 0px;
        z-index: 1000;
        max-width: 350px;
      `;
      return wrapper;
    },
  },
};
</script>

<style scoped>
.indicator-container {
  margin-bottom: 8px;
}
</style>
