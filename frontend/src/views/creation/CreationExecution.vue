<template>
  <BacktestExecutionFields
    v-model:execution="draft.execution"
    v-model:engine="draft.engine"
    :errors="setupErrors"
    @change="touchSetup"
  />
</template>
<script setup lang="ts">
import BacktestExecutionFields from '../BacktestExecutionFields.vue';
import { useCreation } from './creationContext';
const { draft, setupErrors, touchSetup } = useCreation();
</script>
