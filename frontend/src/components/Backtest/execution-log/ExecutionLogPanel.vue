<script setup lang="ts">
import { computed } from 'vue';
import { NButton, NPagination, NScrollbar, NSwitch } from 'naive-ui';
import ExecutionLogTable from './ExecutionLogTable.vue';
import { useExecutionLogStore } from '@/stores/executionLogStore';
const log = useExecutionLogStore();
const label = computed(() =>
  log.selectedRun
    ? `Run #${log.selectedRun.run_ordinal + 1} · ${log.selectedRun.symbols.join(', ')}`
    : '',
);
</script>
<template>
  <section
    v-if="log.selectedRun"
    id="execution-log-panel"
    class="execution-log-panel"
    data-testid="execution-log-panel"
    aria-label="Execution log"
    @keydown.esc.stop="log.isOpen = false"
  >
    <header class="log-header">
      <div class="log-identity"
        ><h2>Trades</h2><span>{{ label }}</span></div
      >
      <label class="order-toggle"
        ><n-switch
          :value="log.includeUnexecuted"
          aria-label="Show unexecuted orders"
          @update:value="log.setIncludeUnexecuted"
        />
        Show unexecuted orders</label
      >
    </header>
    <n-scrollbar class="log-scroll">
      <p
        v-if="log.loading"
        class="notice"
        role="status"
        >Loading execution log…</p
      >
      <div
        v-else-if="log.error"
        class="notice"
        role="alert"
      >
        <p>Execution log unavailable. {{ log.error }}</p>
        <n-button
          size="small"
          @click="log.retry"
          >Retry</n-button
        >
      </div>
      <p
        v-else-if="!log.items.length"
        class="notice"
        role="status"
        >{{
          log.total > 0
            ? 'No records on this page.'
            : log.includeUnexecuted
              ? 'No trades or unexecuted orders in this run.'
              : 'No closed trades in this run.'
        }}</p
      >
      <ExecutionLogTable
        v-else
        :items="log.items"
        :currency="log.selectedRun.currency"
      />
    </n-scrollbar>
    <nav
      v-if="log.total > 10"
      class="floating-pagination"
      aria-label="Execution log pages"
    >
      <n-pagination
        :page="log.page"
        :item-count="log.total"
        :page-size="10"
        :page-slot="5"
        :disabled="log.loading"
        @update:page="log.setPage"
      />
    </nav>
  </section>
</template>
<style scoped>
.execution-log-panel {
  position: relative;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--design-color-panel);
  color: var(--design-color-body);
}
.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 16px 24px;
  border-bottom: 1px solid var(--design-color-border);
}
.log-identity {
  display: flex;
  gap: 16px;
  align-items: baseline;
  min-width: 0;
}
h2 {
  font-size: 18px;
  font-weight: 500;
  margin: 0;
}
.log-identity span {
  color: var(--design-color-muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.order-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}
.log-scroll {
  flex: 1;
  min-height: 0;
}
.notice {
  padding: 24px;
}
.floating-pagination {
  position: absolute;
  bottom: 18px;
  right: 24px;
  padding: 10px 14px;
  background: var(--design-color-fixed);
  border: 1px solid var(--design-color-border);
  border-radius: 999px;
  box-shadow: 0 4px 24px #0005;
  opacity: 0.22;
  transition: opacity 0.18s ease;
}
.floating-pagination:hover,
.floating-pagination:focus-within {
  opacity: 1;
}
@media (hover: none) {
  .floating-pagination {
    opacity: 1;
  }
}
@media (prefers-reduced-motion: reduce) {
  .floating-pagination {
    transition: none;
  }
}
</style>
