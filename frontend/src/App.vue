<template>
  <n-config-provider :theme="darkTheme">
    <main>
      <NavigationPrototypeShell>
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </NavigationPrototypeShell>
    </main>
  </n-config-provider>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { NConfigProvider, darkTheme } from 'naive-ui';
import NavigationPrototypeShell from '@/views/prototype-navigation/NavigationPrototypeShell.vue';
import { wsService } from './utils/websocketService';

export default defineComponent({
  name: 'App',

  components: {
    NConfigProvider,
    NavigationPrototypeShell,
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
