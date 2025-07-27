<template>
  <base-modal ref="baseModal" :modalId="'removeMarket'" :title="'Remove Market'">
    <div>
      <div class="confirmation-content">
        <n-icon size="48" color="#ff6b6b">
          <WarningOutline />
        </n-icon>
        <h3>Are you sure you want to remove this market?</h3>
        <p v-if="market">
          <strong>{{ market.symbol }}</strong>
          <br>
          <span class="market-type">{{ market.market_type }}</span>
          {{ market.exchange }}
        </p>
        <p class="warning-text">
          This action cannot be undone. All associated data for this market will be permanently deleted.
        </p>
      </div>
    </div>

    <template #footer>
      <div class="modal-actions">
        <n-button @click="closeModal" class="button-cancel">Cancel</n-button>
        <n-button
          type="error"
          @click="confirmRemoveCandles"
          :loading="isRemoving"
          class="button-remove"
        >
          Remove Candles
        </n-button>
        <n-button
          type="error"
          @click="confirmRemove"
          :loading="isRemoving"
          class="button-remove"
        >
          Remove Market
        </n-button>
      </div>
    </template>
  </base-modal>
</template>

<script>
import { useMarketsStore } from "@/stores/marketsStore";

import { NIcon, NButton } from "naive-ui";
import { WarningOutline } from "@/icons";
import BaseModal from "@/components/Common/BaseModal.vue";

export default {
  name: "RemoveMarketModal",

  components: {
    NIcon,
    NButton,
    WarningOutline,
    BaseModal,
  },

  props: {
    market: {
      type: Object,
      required: true,
    },
  },

  emits: ["market-removed"],

  data() {
    return {
      marketsStore: useMarketsStore(),
      isRemoving: false,
    };
  },

  methods: {
    closeModal() {
      this.$refs.baseModal.close();
      this.isRemoving = false;
    },

    async confirmRemoveCandles() {
      this.isRemoving = true;

      const response = await this.tryRemoveMarketCandles();
      this.isRemoving = false;

      if (response && response.ok) {
        this.$emit("market-removed", this.market);
        this.closeModal();
      }
    },

    async tryRemoveMarketCandles() {
      try {
        const response = await fetch(`/api/data-accessor/candles/${this.market.symbol_id}`, {
          method: "DELETE",
        });

        return response;
      } catch (error) {
        console.error("Error removing market candles:", error);
      }
    },

    async confirmRemove() {
      if (!this.market) return;

      this.isRemoving = true;

      const response = await this.tryRemoveMarket();
      this.isRemoving = false;
      if (response && response.ok) {
        this.marketsStore.fetch();
        this.closeModal();
      }
    },

    async tryRemoveMarket() {
      try {
        const response = await fetch(`/api/data-accessor/markets/${this.market.symbol_id}`, {
          method: "DELETE",
        });

        return response;
      } catch (error) {
        console.error("Error removing market:", error);
      }
    },
  },
};
</script>

<style scoped>
.confirmation-content {
  text-align: center;
  padding: 20px;
}

p {
  margin: 12px 0;
  line-height: 20px;
}

.market-type {
  font-size: x-small;
  vertical-align: middle;
  text-transform: uppercase;
}

.warning-text {
  font-style: italic;
  font-size: small;
  margin-top: 20px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
