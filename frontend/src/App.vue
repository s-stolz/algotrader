<template>
  <n-config-provider :theme="darkTheme">
    <main>
      <router-view />
    </main>
  </n-config-provider>
</template>

<script>
import { NConfigProvider, darkTheme } from 'naive-ui';

export default {
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
    if (this.$wss) {
      this.$wss.close();
    }
  },
};
</script>

<style>
main {
  padding: 10px;
}
</style>
