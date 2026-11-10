<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { useExecutionLogStore } from '@/stores/executionLogStore';
const executionLog = useExecutionLogStore();
const showTradeAction = computed(() => executionLog.selectedRun !== null);
const tradeActionLabel = computed(
  () =>
    `${executionLog.isOpen ? 'Hide' : 'Show'} trades for Run #` +
    `${(executionLog.selectedRun?.run_ordinal ?? 0) + 1}`,
);

const backtestIconPath = [
  'M9 3h6M10 3v6L4 19a1.3 1.3 0 0 0 1.2 2h13.6',
  'a1.3 1.3 0 0 0 1.2-2L14 9V3M8 14h8M10 17h.01M14 19h.01',
].join('');

const route = useRoute();
const screen = ref<HTMLElement | null>(null);
const isChart = computed(() => route.path === '/');
const destination = computed(() => (isChart.value ? '/backtests' : '/'));
const destinationLabel = computed(() =>
  isChart.value ? 'Open Backtests' : 'Return to Chart',
);

watch(
  isChart,
  () => {
    screen.value?.focus({ preventScroll: true });
  },
  { flush: 'post' },
);
</script>

<template>
  <div class="workspace-navigation">
    <Teleport to="body">
      <div
        :tabindex="showTradeAction ? 0 : undefined"
        :class="[
          {
            'edge-navigation-group': showTradeAction,
          },
          isChart ? 'edge-right' : 'edge-left',
        ]"
      >
        <div class="edge-control-panel">
          <RouterLink
            :key="destination"
            :to="destination"
            :aria-label="destinationLabel"
            aria-controls="workspace-screen"
            class="workspace-edge-link"
            :class="
              isChart
                ? 'workspace-edge-link--right'
                : 'workspace-edge-link--left'
            "
          >
            <span
              class="workspace-edge-face"
              aria-hidden="true"
            >
              <svg
                class="destination-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path
                  v-if="isChart"
                  :d="backtestIconPath"
                />
                <path
                  v-else
                  d="M3 3v18h18M7 15l4-5 4 3 6-8"
                />
              </svg>
              <span class="icon-divider" />
              <svg
                class="direction-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="m9 6 6 6-6 6" />
              </svg>
            </span>
          </RouterLink>
          <button
            v-if="showTradeAction"
            class="edge-trades-action"
            :aria-expanded="executionLog.isOpen"
            :aria-label="tradeActionLabel"
            :title="tradeActionLabel"
            aria-controls="execution-log-panel"
            @click="executionLog.isOpen = !executionLog.isOpen"
          >
            <svg
              viewBox="0 0 24 24"
              width="23"
              height="23"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M4 15h16v6H4z" />
              <path
                :d="
                  executionLog.isOpen
                    ? 'M12 3v8m-4-4 4 4 4-4'
                    : 'M12 11V3m-4 4 4-4 4 4'
                "
              />
            </svg>
          </button>
        </div>
      </div>
    </Teleport>

    <section
      id="workspace-screen"
      ref="screen"
      class="workspace-screen"
      :class="
        isChart ? 'workspace-screen--chart' : 'workspace-screen--backtests'
      "
      :aria-label="isChart ? 'Chart workspace' : 'Backtest workspace'"
      tabindex="-1"
    >
      <slot />
    </section>
  </div>
</template>

<style scoped>
.workspace-navigation {
  position: relative;
  height: 100%;
  padding: var(--design-space-md);
  box-sizing: border-box;
  overflow: hidden;
  color-scheme: dark;
}

.workspace-screen {
  height: 100%;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  outline: none;
}

.workspace-screen--chart {
  overflow: hidden;
  animation: enter-chart 0.28s ease-out;
}

.workspace-screen--backtests {
  animation: enter-backtests 0.28s ease-out;
}

.workspace-edge-link {
  position: fixed;
  top: 50%;
  transform: translateY(-50%);
  z-index: 1100;
  width: 64px;
  height: 176px;
  color: var(--design-color-interactive);
}

.workspace-edge-link::before {
  content: '';
  position: absolute;
  inset-block: 0;
  width: 5px;
  background: var(--design-color-edge-rail);
  border: 1px solid var(--design-color-edge-border);
  box-sizing: border-box;
}

.workspace-edge-link--left {
  left: 0;
}
.workspace-edge-link--right {
  right: 0;
}
.workspace-edge-link--left::before {
  left: 0;
  border-radius: 0 5px 5px 0;
}
.workspace-edge-link--right::before {
  right: 0;
  border-radius: 5px 0 0 5px;
}

.workspace-edge-face {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--design-space-xl);
  box-sizing: border-box;
  background: var(--design-color-fixed);
  border: 1px solid var(--design-color-border);
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
}

.workspace-edge-link--left .workspace-edge-face {
  border-left: none;
  border-radius: 0 var(--design-radius-edge) var(--design-radius-edge) 0;
  transform: translateX(-100%);
}

.workspace-edge-link--right .workspace-edge-face {
  border-right: none;
  border-radius: var(--design-radius-edge) 0 0 var(--design-radius-edge);
  transform: translateX(100%);
}

/* The hit area stays at the final size; only entry animates, so exit hides immediately. */
.workspace-edge-link:hover .workspace-edge-face,
.workspace-edge-link:focus-visible .workspace-edge-face {
  opacity: 1;
  visibility: visible;
  transform: translateX(0);
  transition:
    transform 0.14s ease-out,
    opacity 0.14s;
}

.workspace-edge-link:hover::before,
.workspace-edge-link:focus-visible::before {
  opacity: 0;
}
.workspace-edge-link:focus-visible {
  outline: none;
}
.workspace-edge-link:focus-visible .workspace-edge-face {
  outline: 2px solid currentColor;
  outline-offset: -4px;
}

.destination-icon {
  width: 23px;
  height: 23px;
}
.direction-icon {
  width: 21px;
  height: 21px;
}
.workspace-edge-link--left .direction-icon {
  transform: rotate(180deg);
}
.icon-divider {
  width: 14px;
  height: 1px;
  background: var(--design-color-border);
}

@keyframes enter-chart {
  from {
    transform: translateX(-100px);
    opacity: 0.4;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes enter-backtests {
  from {
    transform: translateX(100px);
    opacity: 0.4;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .workspace-screen {
    animation: none;
  }
  .workspace-edge-link:hover .workspace-edge-face,
  .workspace-edge-link:focus-visible .workspace-edge-face {
    transition: none;
  }
}
.edge-navigation-group {
  position: fixed;
  top: 50%;
  width: 64px;
  height: 224px;
  transform: translateY(-50%);
  z-index: 1100;
}
.edge-left {
  left: 0;
}
.edge-right {
  right: 0;
}
/* One moving surface keeps both actions aligned throughout the reveal. */
.edge-control-panel {
  display: contents;
}
.edge-navigation-group::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  width: 5px;
  background: var(--design-color-edge-rail);
  border: 1px solid var(--design-color-edge-border);
  box-sizing: border-box;
}
.edge-left::before {
  left: 0;
}
.edge-right::before {
  right: 0;
}
.edge-navigation-group .edge-control-panel {
  display: flex;
  flex-direction: column;
  position: absolute;
  inset: 0;
  background: var(--design-color-fixed);
  border: 1px solid var(--design-color-border);
  opacity: 0;
  visibility: hidden;
}
.edge-left .edge-control-panel {
  transform: translateX(-100%);
  border-radius: 0 16px 16px 0;
}
.edge-right .edge-control-panel {
  transform: translateX(100%);
  border-radius: 16px 0 0 16px;
}
.edge-navigation-group:hover .edge-control-panel,
.edge-navigation-group:focus-visible .edge-control-panel,
.edge-navigation-group:has(:focus-visible) .edge-control-panel {
  opacity: 1;
  visibility: visible;
  transform: translateX(0);
  transition:
    transform 0.14s ease-out,
    opacity 0.14s;
}
.edge-navigation-group:hover::before,
.edge-navigation-group:focus-visible::before,
.edge-navigation-group:has(:focus-visible)::before {
  opacity: 0;
}
.edge-navigation-group .workspace-edge-link {
  display: block;
  position: relative;
  top: auto;
  transform: none;
  width: 100%;
  height: 176px;
  flex-shrink: 0;
}
.edge-navigation-group .workspace-edge-link::before {
  display: none;
}
.edge-navigation-group .workspace-edge-face {
  opacity: 1;
  visibility: inherit;
  transform: none;
  transition: none;
  background: transparent;
  border: 0;
  border-radius: 0;
}
.edge-trades-action {
  width: 100%;
  flex: 1;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  border-top: 1px solid var(--design-color-border);
  background: transparent;
  color: var(--design-color-interactive);
  font: inherit;
  cursor: pointer;
  border-radius: inherit;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
}
.edge-trades-action:hover {
  background: var(--design-color-hover);
}
.edge-trades-action:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: -4px;
}
@media (prefers-reduced-motion: reduce) {
  .edge-navigation-group:hover .edge-control-panel,
  .edge-navigation-group:focus-visible .edge-control-panel,
  .edge-navigation-group:has(:focus-visible) .edge-control-panel {
    transition: none;
  }
}
</style>
