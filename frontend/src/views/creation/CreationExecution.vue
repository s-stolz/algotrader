<template>
  <BacktestExecutionFields
    v-model:execution="draft.execution"
    v-model:engine="draft.engine"
    v-model:allowed-directions="selections.allowedDirections"
  />
</template>
<script setup lang="ts">
import BacktestExecutionFields from '../BacktestExecutionFields.vue';
import { useCreation } from './creationContext';
const { draft, selections } = useCreation();
</script>
