<template>
  <div class="creation-review">
    <section
      class="preview-section"
      aria-label="Backtest preview"
    >
      <div class="section-header">
        <n-tag
          v-if="candidateLimit"
          size="small"
          :bordered="false"
          >Limit: {{ candidateLimit }} candidates</n-tag
        >
      </div>
      <p
        v-if="previewError"
        role="alert"
        >{{ previewError }}</p
      >
      <p
        v-if="previewPending"
        role="status"
        >Refreshing preview…</p
      >
      <section
        v-if="preview"
        class="preview-review"
        data-testid="selections-review"
      >
        <dl class="preview-counts">
          <div
            ><dt>Raw candidates</dt><dd>{{ preview.raw_count }}</dd></div
          >
          <div
            ><dt>Ready</dt><dd>{{ preview.ready_count }}</dd></div
          >
          <div
            ><dt>Excluded</dt><dd>{{ preview.excluded_count }}</dd></div
          >
        </dl>

        <label class="preview-filter"
          >Status
          <BaseSelect
            v-model:value="previewFilter"
            :options="previewFilterOptions"
            data-testid="selections-filter"
          />
        </label>
        <n-scrollbar
          class="preview-table-scroll"
          :content-style="{ paddingRight: '8px', boxSizing: 'border-box' }"
        >
          <BaseDataTable
            :columns="previewColumns"
            :data="filteredCandidates"
            :pagination="{ pageSize: 10 }"
            size="small"
            table-layout="auto"
            data-testid="selections-candidates"
          />
        </n-scrollbar>
      </section>
    </section>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue';
import { NTag, NScrollbar } from 'naive-ui';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import { previewFilterOptions } from './creationOptions';
import { previewColumns as buildPreviewColumns } from './creationPreview';
import { useCreation } from './creationContext';
const {
  candidateLimit,
  previewError,
  previewPending,
  preview,
  previewFilter,
  selectedStrategy,
} = useCreation();
const filteredCandidates = computed(
  () =>
    preview.value?.candidates.filter(
      (row) =>
        previewFilter.value === 'all' || row.status === previewFilter.value,
    ) ?? [],
);
const previewColumns = computed(() =>
  buildPreviewColumns(selectedStrategy.value),
);
</script>

<style scoped>
.creation-review {
  height: 100%;
  min-height: 0;
}
</style>
