<script setup lang="ts">
import { ref } from 'vue';
import { NButton, NDrawerContent } from 'naive-ui';
import BaseDrawer from '@/components/Common/BaseDrawer.vue';
const open = ref(false);
</script>
<template>
  <n-button type="primary" @click="open = true">＋ Create Backtest</n-button>
  <BaseDrawer v-model:show="open" :width="440" style="max-width: 100vw">
    <n-drawer-content title="Create Backtest" closable>
      <p class="preview-label">NAVIGATION PROTOTYPE</p>
      <h2>Your next experiment starts here.</h2>
      <p>This previews where the existing creation drawer opens. No backtest will be submitted.</p>
      <div class="draft-preview"><span>01</span> Choose a strategy</div>
      <div class="draft-preview"><span>02</span> Set markets and timeframes</div>
      <div class="draft-preview"><span>03</span> Review your experiment</div>
      <template #footer><n-button @click="open = false">Back to workspace</n-button></template>
    </n-drawer-content>
  </BaseDrawer>
</template>
<style scoped>
.preview-label { color: #66dfbd; letter-spacing: 2px; font-size: 10px; } h2 { font-size: 23px; } p { color: #94a4b6; line-height: 1.7; }
.draft-preview { border-top: 1px solid #2b3745; padding: 22px 0; } .draft-preview span { color: #66dfbd; margin-right: 14px; }
</style>
