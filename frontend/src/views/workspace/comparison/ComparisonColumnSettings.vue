<template>
  <div class="comparison-controls">
    <span class="column-count"
      >{{ columnSettings.visibleKeys.length }} columns shown</span
    >
    <BasePopover
      trigger="click"
      placement="bottom-end"
      :width="500"
      :style="{
        maxWidth: 'calc(100vw - 32px)',
        marginBottom: '16px',
      }"
    >
      <template #trigger>
        <n-button
          size="small"
          round
          data-testid="comparison-columns"
          aria-label="Run analysis columns"
        >
          <template #icon><n-icon :component="OptionsOutline" /></template
          >Columns
        </n-button>
      </template>
      <div class="column-popover">
        <section
          v-for="group in columnGroups"
          :key="group.title"
          :aria-label="group.title"
          class="column-group"
        >
          <div class="column-group-heading">
            <h3>{{ group.title }}</h3>
            <BaseCheckbox
              :checked="group.enabled"
              :indeterminate="group.indeterminate"
              :data-testid="`comparison-group-${group.title}`"
              :aria-label="`Show all ${group.title} columns`"
              @update:checked="setColumnGroup(group.columns, $event)"
            />
          </div>
          <div class="column-options">
            <BaseCheckbox
              v-for="column in group.columns"
              :key="column.key"
              :checked="columnSettings.visibleKeys.includes(column.key)"
              :data-testid="`comparison-column-${column.key}`"
              @update:checked="setColumn(column.key, $event)"
            >
              {{ column.title }}
            </BaseCheckbox>
          </div>
        </section>
        <div
          v-if="!hasDefaultColumns"
          class="column-popover-footer"
        >
          <n-button
            size="small"
            round
            data-testid="comparison-reset-columns"
            @click="resetColumns"
          >
            <template #icon><n-icon :component="RefreshOutline" /></template
            >Reset to default
          </n-button>
        </div>
      </div>
    </BasePopover>
  </div>
</template>
<script setup lang="ts">
import { NButton, NIcon } from 'naive-ui';
import { OptionsOutline, RefreshOutline } from '@vicons/ionicons5';
import BasePopover from '@/components/Common/BasePopover.vue';
import BaseCheckbox from '@/components/Common/BaseCheckbox.vue';
import type { WorkspaceComparison } from './useWorkspaceComparison';
const props = defineProps<{ comparison: WorkspaceComparison }>();
const {
  columnSettings,
  columnGroups,
  hasDefaultColumns,
  setColumnGroup,
  setColumn,
  resetColumns,
} = props.comparison;
</script>
<style scoped>
.comparison-controls {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  margin: 22px 0 16px;
}
.column-count {
  color: #94a3b8;
  align-self: center;
}
.column-popover {
  display: grid;
  gap: 18px;
  width: 100%;
  padding: 4px;
  box-sizing: border-box;
}
.column-popover-footer {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--surface-border);
  padding-top: 16px;
}
.column-group + .column-group {
  border-top: 1px solid var(--surface-border);
  padding-top: 16px;
}
.column-group-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.column-group h3 {
  margin: 0;
  color: #9aafbf;
  font-size: 12px;
  font-weight: 600;
}
.column-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
  margin-top: 10px;
}
@media (max-width: 480px) {
  .column-options {
    grid-template-columns: 1fr;
  }
}
</style>
