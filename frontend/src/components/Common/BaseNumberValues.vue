<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue';
import { NTag } from 'naive-ui';
import BaseSelect from './BaseSelect.vue';

const props = defineProps<{ value: number[]; label: string; integer?: boolean }>();
const emit = defineEmits<{ 'update:value': [value: number[]]; 'update:valid': [valid: boolean] }>();
const search = ref('');
onUnmounted(() => emit('update:valid', true));
const issue = computed(() => {
  const text = search.value.trim();
  if (!text) return '';
  if (!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(text) || !Number.isFinite(Number(text))) {
    return 'Enter a valid number.';
  }
  return props.integer && !Number.isInteger(Number(text)) ? 'Enter a whole number.' : '';
});
function updateSearch(value: string): void {
  search.value = value;
  emit('update:valid', !issue.value && !value.trim());
}
function updateValues(values: Array<string | number>): void {
  if (issue.value) return;
  emit('update:value', values.map(Number));
  updateSearch('');
}
</script>
<template>
  <div class="number-values">
    <span class="values-label">Values<n-tag round size="small" :bordered="false" :aria-label="`${value.length} values`">{{ value.length }}</n-tag></span>
    <BaseSelect
      :value="value"
      multiple
      filterable
      tag
      max-tag-count="responsive"
      :show-arrow="false"
      :options="value.map(number => ({ label: String(number), value: number }))"
      :filter="(pattern, option) => !pattern.trim() || (!issue && Number(pattern) === option.value)"
      :on-create="text => ({ label: String(Number(text)), value: Number(text) })"
      :status="issue ? 'error' : undefined"
      :input-props="{ 'aria-label': label }"
      placeholder="Add value"
      @search="updateSearch"
      @update:value="updateValues"
    />
    <small v-if="issue" role="alert">{{ issue }}</small>
  </div>
</template>
<style scoped>
.number-values { display: grid; gap: 7px; min-width: 0; }
.values-label { display: flex; align-items: center; gap: 7px; font-size: 12px; }
small { color: #ffb4b4; }
</style>
