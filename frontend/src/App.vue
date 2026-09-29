<template>
  <n-config-provider :theme="darkTheme">
    <WorkspaceNavigation>
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </WorkspaceNavigation>
  </n-config-provider>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { NConfigProvider, darkTheme } from 'naive-ui';
import WorkspaceNavigation from '@/components/Workspace/WorkspaceNavigation.vue';
import { wsService } from './utils/websocketService';

export default defineComponent({
  name: 'App',

  components: {
    NConfigProvider,
    WorkspaceNavigation,
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
