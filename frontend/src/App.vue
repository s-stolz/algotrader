<template>
  <DesignScope>
    <div class="app-split-workspace">
      <n-split
        direction="vertical"
        :size="executionLog.consumesSpace ? executionLog.splitSize : 1"
        :disabled="!executionLog.consumesSpace"
        :resize-trigger-size="executionLog.consumesSpace ? 10 : 0"
        :min="executionLog.consumesSpace ? 0.2 : 0"
        :max="executionLog.consumesSpace ? 0.8 : 1"
        @update:size="executionLog.resize"
      >
        <template #1>
          <div class="primary-workspace">
            <WorkspaceNavigation>
              <router-view v-slot="{ Component }">
                <keep-alive>
                  <component :is="Component" />
                </keep-alive>
              </router-view>
            </WorkspaceNavigation>
            <BacktestActivity
              v-if="$route.path.startsWith('/backtests')"
              ref="activity"
              @inspect="
                $router.push(`/backtests/${encodeURIComponent($event)}`)
              "
            />
          </div>
        </template>
        <template #resize-trigger
          ><div
            v-if="executionLog.consumesSpace"
            class="trade-split-grip"
            title="Drag to resize workspace and trades"
            role="separator"
            tabindex="0"
            aria-orientation="horizontal"
            aria-label="Resize workspace and trades"
            :aria-valuenow="Math.round(executionLog.splitSize * 100)"
            :aria-valuemin="20"
            :aria-valuemax="80"
            @keydown.up.prevent="
              executionLog.resize(executionLog.splitSize - 0.05)
            "
            @keydown.down.prevent="
              executionLog.resize(executionLog.splitSize + 0.05)
            "
            @keydown.home.prevent="executionLog.resize(0.2)"
            @keydown.end.prevent="executionLog.resize(0.8)"
            ><span /></div
        ></template>
        <template #2
          ><ExecutionLogPanel
            v-if="hasOpenedExecutionLog"
            v-show="executionLog.consumesSpace"
        /></template>
      </n-split>
    </div>
  </DesignScope>
</template>

<script lang="ts">
import {
  defineAsyncComponent,
  defineComponent,
  provide,
  ref,
  watch,
} from 'vue';
import { refreshBacktestActivityKey } from '@/components/Backtest/activity/activityContext';
import { NSplit } from 'naive-ui';
import { useExecutionLogStore } from '@/stores/executionLogStore';
import DesignScope from '@/components/Common/DesignScope.vue';
import WorkspaceNavigation from '@/components/Workspace/WorkspaceNavigation.vue';
import { wsService } from './utils/websocketService';

const BacktestActivity = defineAsyncComponent(
  () => import('@/components/Backtest/activity/BacktestActivity.vue'),
);

const ExecutionLogPanel = defineAsyncComponent(
  () => import('@/components/Backtest/execution-log/ExecutionLogPanel.vue'),
);

export default defineComponent({
  name: 'App',

  components: {
    DesignScope,
    BacktestActivity,
    NSplit,
    ExecutionLogPanel,
    WorkspaceNavigation,
  },

  setup() {
    const activity = ref<InstanceType<typeof BacktestActivity> | null>(null);
    provide(refreshBacktestActivityKey, () => {
      void activity.value?.refresh();
    });
    const executionLog = useExecutionLogStore();
    const hasOpenedExecutionLog = ref(false);
    watch(
      () => executionLog.consumesSpace,
      (visible) => {
        if (visible) hasOpenedExecutionLog.value = true;
      },
      { immediate: true },
    );
    return { executionLog, activity, hasOpenedExecutionLog };
  },

  beforeUnmount() {
    wsService.close();
  },
});
</script>

<style scoped>
.app-split-workspace {
  position: fixed;
  inset: 0;
}
.primary-workspace {
  position: relative;
  height: 100%;
}
.trade-split-grip {
  height: 100%;
  display: grid;
  place-items: center;
  background: var(--design-color-border);
  cursor: ns-resize;
}
.trade-split-grip span {
  width: 44px;
  height: 3px;
  border-radius: 3px;
  background: var(--design-color-muted);
}
.trade-split-grip:focus-visible {
  outline: 2px solid var(--design-color-interactive);
  outline-offset: -2px;
}
.trade-split-grip:hover {
  background: var(--design-color-selected);
}
</style>
