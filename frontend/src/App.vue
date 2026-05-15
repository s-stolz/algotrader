<template>
  <n-config-provider :theme="darkTheme">
    <main>
      <router-view />
    </main>
  </n-config-provider>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { NConfigProvider, darkTheme } from 'naive-ui';
import { wsService } from './utils/websocketService';

export default defineComponent({
  name: 'App',

  components: {
    NConfigProvider,
  },

  data() {
    return {
      darkTheme,
    };
  },

  beforeUnmount() {
    wsService.close();
  },
});
</script>

<style>
main {
  padding: 10px;
}
</style>
