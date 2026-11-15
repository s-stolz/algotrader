<template>
  <tr
    :aria-selected="isSelected"
    @click="onRowClick"
  >
    <td class="symbol-cell">{{ market.symbol }}</td>
    <td class="actions-cell">
      <span class="market-info">
        <span class="market-type">{{ market.market_type }}</span>
        <span class="market-type">{{
          market.source_type === 'broker' ? 'Broker' : 'Custom'
        }}</span>
        {{ market.exchange }}
      </span>
      <BaseDropdown
        :options="menuOptions"
        trigger="click"
        @select="onMenuSelect"
      >
        <n-button
          text
          circle
          size="small"
          :aria-label="`Actions for ${market.symbol}`"
          @click.stop
        >
          <n-icon size="20">
            <EllipsisHorizontalCircleOutline />
          </n-icon>
        </n-button>
      </BaseDropdown>
    </td>
  </tr>
</template>

<script setup lang="ts">
import { computed, h } from 'vue';
import BaseDropdown from '@/components/Common/BaseDropdown.vue';
import { NButton, NIcon, type DropdownOption } from 'naive-ui';

import {
  CloudUploadOutline,
  CloudDownloadOutline,
  CreateOutline,
  EllipsisHorizontalCircleOutline,
  TrashOutline,
} from '@/icons';
import type { Market } from '@/types/contracts';

defineOptions({
  name: 'SymbolRow',
});

const props = defineProps<{
  market: Market;
  isSelected?: boolean;
}>();

const emit = defineEmits<{
  (event: 'market-click', market: Market): void;
  (event: 'remove-market', market: Market): void;
  (event: 'upload-data', market: Market): void;
  (event: 'edit-market', market: Market): void;
  (event: 'download-history', market: Market): void;
}>();

const menuOptions = computed<DropdownOption[]>(() => [
  {
    label: 'Edit symbol',
    key: 'edit',
    icon: () => h(NIcon, null, { default: () => h(CreateOutline) }),
  },
  {
    label:
      props.market.source_type === 'broker'
        ? 'Download historical data'
        : 'Upload Data',
    key: props.market.source_type === 'broker' ? 'history' : 'upload',
    icon: () =>
      h(NIcon, null, {
        default: () =>
          h(
            props.market.source_type === 'broker'
              ? CloudDownloadOutline
              : CloudUploadOutline,
          ),
      }),
  },
  {
    label: 'Remove',
    key: 'remove',
    icon: () => h(NIcon, null, { default: () => h(TrashOutline) }),
  },
]);

function onRowClick(): void {
  emit('market-click', props.market);
}

function onMenuSelect(key: string | number): void {
  if (key === 'edit') {
    emit('edit-market', props.market);
  } else if (key === 'remove') {
    emit('remove-market', props.market);
  } else if (key === 'history' && props.market.source_type === 'broker') {
    emit('download-history', props.market);
  } else if (key === 'upload' && props.market.source_type !== 'broker') {
    emit('upload-data', props.market);
  }
}
</script>

<style scoped>
tr {
  width: 100%;
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
  gap: var(--design-space-sm);
  line-height: 20px;
}

.market-info {
  display: flex;
  align-items: center;
  gap: var(--design-space-xs);
}

td {
  padding: var(--design-space-md) var(--design-space-lg);
  line-height: 20px;
}

.market-type {
  font-size: var(--design-text-secondary);
  color: var(--design-color-muted);
  vertical-align: middle;
}

tr[aria-selected='true'] .symbol-cell {
  box-shadow: inset 2px 0 var(--design-color-interactive);
}
</style>
