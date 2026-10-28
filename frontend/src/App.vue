<template>
  <DesignScope>
    <WorkspaceNavigation>
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </WorkspaceNavigation>
  </DesignScope>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import DesignScope from '@/components/Common/DesignScope.vue';
import WorkspaceNavigation from '@/components/Workspace/WorkspaceNavigation.vue';
import { wsService } from './utils/websocketService';

export default defineComponent({
  name: 'App',

  components: {
    DesignScope,
    WorkspaceNavigation,
  },

  beforeUnmount() {
    wsService.close();
  },
});
</script>
