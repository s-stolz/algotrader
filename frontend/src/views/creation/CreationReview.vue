<template>
  <p
    v-if="submitError"
    role="alert"
    >{{ submitError }}</p
  >
  <section
    v-if="isSweep"
    class="preview-section"
    aria-labelledby="preview-heading"
  >
    <div class="section-header">
      <h3 id="preview-heading">Sweep preview</h3>
      <n-tag
        v-if="sweepLimit"
        size="small"
        :bordered="false"
        >Limit: {{ sweepLimit }} candidates</n-tag
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
      data-testid="sweep-review"
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
      <p class="section-description"
        >Candidate # preserves the full grid order. Ready member # is contiguous
        after exclusions. Sorting and filtering only change this review
        table.</p
      >
      <label class="preview-filter"
        >Status
        <BaseSelect
          v-model:value="previewFilter"
          :options="previewFilterOptions"
          data-testid="sweep-filter"
        />
      </label>
      <BaseDataTable
        :columns="previewColumns"
        :data="filteredCandidates"
        :pagination="{ pageSize: 20 }"
        :scroll-x="previewColumns.length * 150"
        data-testid="sweep-candidates"
      />
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import BaseDataTable from '@/components/Common/BaseDataTable.vue';
import { NTag } from 'naive-ui';
import { previewFilterOptions } from './creationOptions';
import { previewColumns as buildPreviewColumns } from './creationPreview';
import { useCreation } from './creationContext';
const {
  submitError,
  isSweep,
  sweepLimit,
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
