<script setup lang="ts">
import { NConfigProvider, darkTheme } from 'naive-ui';
import { designCssProperties } from '@/design/cssProperties';
import { designThemeOverrides } from '@/design/naiveTheme';
</script>

<template>
  <NConfigProvider
    class="design-scope"
    :theme="darkTheme"
    :theme-overrides="designThemeOverrides"
    :style="designCssProperties"
  >
    <slot />
  </NConfigProvider>
</template>

<style scoped>
.design-scope {
  display: contents;
  font-family: var(--design-font-ui);
  font-size: var(--design-text-body);
  color: var(--design-color-body);
}
</style>
