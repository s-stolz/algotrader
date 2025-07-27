<template>
  <div v-if="headerLine.length > 0" class="upload-data-preview">
    <n-scrollbar x-scrollable>
      <n-table :bordered="true" :single-line="false">
        <tbody>
          <tr>
            <td v-for="(column, index) in headerLine" :key="index">{{ column }}</td>
          </tr>
          <tr>
            <td v-for="(column, index) in headerLine" :key="index">
              <n-select
                v-model:value="columnMapping[index]"
                :options="columnOptions"
                placeholder="Select field"
                clearable
                @update:value="(value) => updateColumnMapping(index, value)"
              />
            </td>
          </tr>
        </tbody>
      </n-table>
    </n-scrollbar>
  </div>
</template>

<script>
import { NSelect, NTable, NScrollbar } from "naive-ui";

export default {
  name: "UploadDataPreview",

  components: {
    NSelect,
    NTable,
    NScrollbar,
  },

  props: {
    headerLine: {
      type: Array,
      required: true,
    },
    columnMapping: {
      type: Object,
      required: true,
    },
  },

  emits: ["update:column-mapping"],

  data() {
    return {
      columnOptions: [
        { label: "Timestamp", value: "timestamp" },
        { label: "Date", value: "date" },
        { label: "Time", value: "time" },
        { label: "Open", value: "open" },
        { label: "High", value: "high" },
        { label: "Low", value: "low" },
        { label: "Close", value: "close" },
        { label: "Volume", value: "volume" },
        { label: "Ignore", value: null },
      ],
    };
  },

  methods: {
    updateColumnMapping(index, value) {
      const newMapping = { ...this.columnMapping };
      newMapping[index] = value;
      this.$emit("update:column-mapping", newMapping);
    },
  },
};
</script>

<style scoped>
.upload-data-preview {
  margin-bottom: 24px;
}

td {
  min-width: 125px;
}
</style>