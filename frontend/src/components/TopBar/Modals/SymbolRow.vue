<template>
  <tr @click="onRowClick">
    <td class="symbol-cell">{{ market.symbol }}</td>
    <td class="actions-cell">
      <span class="market-info">
        <span class="market-type">{{ market.market_type }}</span>
        {{ market.exchange }}
      </span>
      <n-dropdown
        :options="menuOptions"
        trigger="click"
        @select="onMenuSelect"
      >
        <n-button
          text
          size="small"
          @click.stop
        >
          <n-icon size="20">
            <EllipsisHorizontalCircleOutline />
          </n-icon>
        </n-button>
      </n-dropdown>
    </td>
  </tr>
</template>

<script>
import { h } from "vue";
import { NIcon, NButton, NDropdown } from "naive-ui";
import { TrashOutline, CloudUploadOutline, EllipsisHorizontalCircleOutline } from "@/icons";

export default {
  name: "SymbolRow",

  components: {
    NIcon,
    NButton,
    NDropdown,
    // eslint-disable-next-line vue/no-unused-components
    TrashOutline,
    // eslint-disable-next-line vue/no-unused-components
    CloudUploadOutline,
    EllipsisHorizontalCircleOutline,
  },

  props: {
    market: {
      type: Object,
      required: true,
    },
  },

  emits: ["market-click", "remove-market", "upload-data"],

  computed: {
    menuOptions() {
      return [
        {
          label: "Upload Data",
          key: "upload",
          icon: () => h(NIcon, null, { default: () => h(CloudUploadOutline) }),
        },
        {
          label: "Remove",
          key: "remove",
          icon: () => h(NIcon, null, { default: () => h(TrashOutline) }),
        },
      ];
    },
  },

  methods: {
    onRowClick() {
      this.$emit("market-click", this.market);
    },

    onMenuSelect(key) {
      if (key === "remove") {
        this.$emit("remove-market", this.market);
      } else if (key === "upload") {
        this.$emit("upload-data", this.market);
      }
    },
  },
};
</script>

<style scoped>
tr {
  padding: 5px 15px;
  width: calc(100% - 30px);
  display: flex;
  justify-content: space-between;
  cursor: pointer;
}

.symbol-cell {
  flex: 1;
  line-height: 20px;
}

.actions-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  line-height: 20px;
}

.market-info {
  display: flex;
  align-items: center;
  gap: 4px;
}

td {
  line-height: 20px;
}

.market-type {
  font-size: x-small;
  vertical-align: middle;
}

tr:hover {
  background-color: #36363661;
}
</style>
