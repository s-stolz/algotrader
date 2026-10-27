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
        maxWidth: 'calc(100vw - var(--design-space-xxl))',
        marginBottom: 'var(--design-space-lg)',
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
  gap: var(--design-space-lg);
  margin: var(--design-space-xl) 0 var(--design-space-lg);
}
.column-count {
  color: var(--design-color-muted);
  align-self: center;
}
.column-popover {
  display: grid;
  gap: var(--design-space-lg);
  width: 100%;
  padding: var(--design-space-xs);
  box-sizing: border-box;
}
.column-popover-footer {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--design-color-border);
  padding-top: var(--design-space-lg);
}
.column-group + .column-group {
  border-top: 1px solid var(--design-color-border);
  padding-top: var(--design-space-lg);
}
.column-group-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--design-space-md);
}
.column-group h3 {
  margin: 0;
  color: var(--design-color-muted);
  font-size: var(--design-text-secondary);
  font-weight: 600;
}
.column-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--design-space-sm) var(--design-space-lg);
  margin-top: var(--design-space-sm);
}
@media (max-width: 480px) {
  .column-options {
    grid-template-columns: 1fr;
  }
}
</style>
