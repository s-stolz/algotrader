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
                :value="columnMapping[index]"
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

<script setup lang="ts">
import { NScrollbar, NSelect, NTable, type SelectOption } from 'naive-ui';

import type { UploadColumnField, UploadColumnMapping } from '@/types/contracts';

defineOptions({
  name: 'UploadDataPreview',
});

const props = defineProps<{
  columnMapping: UploadColumnMapping;
  headerLine: string[];
}>();

const emit = defineEmits<{
  (event: 'update:column-mapping', mapping: UploadColumnMapping): void;
}>();

const columnOptions: SelectOption[] = [
  { label: 'Timestamp', value: 'timestamp' },
  { label: 'Date', value: 'date' },
  { label: 'Time', value: 'time' },
  { label: 'Open', value: 'open' },
  { label: 'High', value: 'high' },
  { label: 'Low', value: 'low' },
  { label: 'Close', value: 'close' },
  { label: 'Volume', value: 'volume' },
  { label: 'Ignore', value: '' },
];

function updateColumnMapping(index: number, value: UploadColumnField | '' | null): void {
  const newMapping: UploadColumnMapping = { ...props.columnMapping };
  newMapping[index] = value;
  emit('update:column-mapping', newMapping);
}
</script>

<style scoped>
.upload-data-preview {
  margin-bottom: 24px;
}

td {
  min-width: 125px;
}
</style>
