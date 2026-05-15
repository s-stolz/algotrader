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

<script setup lang="ts">
import { h } from 'vue';
import { NButton, NDropdown, NIcon, type DropdownOption } from 'naive-ui';

import { CloudUploadOutline, EllipsisHorizontalCircleOutline, TrashOutline } from '@/icons';
import type { Market } from '@/types/contracts';

defineOptions({
  name: 'SymbolRow',
});

const props = defineProps<{
  market: Market;
}>();

const emit = defineEmits<{
  (event: 'market-click', market: Market): void;
  (event: 'remove-market', market: Market): void;
  (event: 'upload-data', market: Market): void;
}>();

const menuOptions: DropdownOption[] = [
  {
    label: 'Upload Data',
    key: 'upload',
    icon: () => h(NIcon, null, { default: () => h(CloudUploadOutline) }),
  },
  {
    label: 'Remove',
    key: 'remove',
    icon: () => h(NIcon, null, { default: () => h(TrashOutline) }),
  },
];

function onRowClick(): void {
  emit('market-click', props.market);
}

function onMenuSelect(key: string | number): void {
  if (key === 'remove') {
    emit('remove-market', props.market);
  } else if (key === 'upload') {
    emit('upload-data', props.market);
  }
}
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
