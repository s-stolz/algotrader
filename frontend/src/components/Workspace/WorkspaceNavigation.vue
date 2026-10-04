<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

const route = useRoute();
const screen = ref<HTMLElement | null>(null);
const isChart = computed(() => route.path === '/');
const destination = computed(() => isChart.value ? '/backtests' : '/');
const destinationLabel = computed(() => isChart.value ? 'Open Backtests' : 'Return to Chart');

watch(isChart, () => {
  screen.value?.focus({ preventScroll: true });
}, { flush: 'post' });
</script>

<template>
  <div class="workspace-navigation">
    <RouterLink
      :key="destination"
      :to="destination"
      :aria-label="destinationLabel"
      aria-controls="workspace-screen"
      class="workspace-edge-link"
      :class="isChart ? 'workspace-edge-link--right' : 'workspace-edge-link--left'"
    >
      <span class="workspace-edge-face" aria-hidden="true">
        <svg class="destination-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path v-if="isChart" d="M9 3h6M10 3v6L4 19a1.3 1.3 0 0 0 1.2 2h13.6a1.3 1.3 0 0 0 1.2-2L14 9V3M8 14h8M10 17h.01M14 19h.01" />
          <path v-else d="M3 3v18h18M7 15l4-5 4 3 6-8" />
        </svg>
        <span class="icon-divider" />
        <svg class="direction-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="m9 6 6 6-6 6" />
        </svg>
      </span>
    </RouterLink>
    <section
      id="workspace-screen"
      ref="screen"
      class="workspace-screen"
      :class="isChart ? 'workspace-screen--chart' : 'workspace-screen--backtests'"
      :aria-label="isChart ? 'Chart workspace' : 'Backtest workspace'"
      tabindex="-1"
    >
      <slot />
    </section>
  </div>
</template>

<style scoped>
.workspace-navigation {
  position: fixed;
  inset: 0;
  padding: 10px;
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
  animation: enter-chart .28s ease-out;
}

.workspace-screen--backtests {
  animation: enter-backtests .28s ease-out;
}

.workspace-edge-link {
  position: fixed;
  top: 50%;
  transform: translateY(-50%);
  z-index: 20;
  width: 64px;
  height: 176px;
  color: #66dfbd;
}

.workspace-edge-link::before {
  content: '';
  position: absolute;
  inset-block: 0;
  width: 5px;
  background: #71879b66;
  border: 1px solid #96b4c833;
  box-sizing: border-box;
}

.workspace-edge-link--left { left: 0; }
.workspace-edge-link--right { right: 0; }
.workspace-edge-link--left::before { left: 0; border-radius: 0 5px 5px 0; }
.workspace-edge-link--right::before { right: 0; border-radius: 5px 0 0 5px; }

.workspace-edge-face {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  box-sizing: border-box;
  background: var(--surface-fixed);
  border: 1px solid #66dfbd60;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
}

.workspace-edge-link--left .workspace-edge-face {
  border-left: none;
  border-radius: 0 16px 16px 0;
  transform: translateX(-100%);
}

.workspace-edge-link--right .workspace-edge-face {
  border-right: none;
  border-radius: 16px 0 0 16px;
  transform: translateX(100%);
}

/* The hit area stays at the final size; only entry animates, so exit hides immediately. */
.workspace-edge-link:hover .workspace-edge-face,
.workspace-edge-link:focus-visible .workspace-edge-face {
  opacity: 1;
  visibility: visible;
  transform: translateX(0);
  transition: transform .14s ease-out, opacity .14s;
}

.workspace-edge-link:hover::before,
.workspace-edge-link:focus-visible::before { opacity: 0; }
.workspace-edge-link:focus-visible { outline: none; }
.workspace-edge-link:focus-visible .workspace-edge-face {
  outline: 2px solid currentColor;
  outline-offset: -4px;
}

.destination-icon { width: 23px; height: 23px; }
.direction-icon { width: 21px; height: 21px; }
.workspace-edge-link--left .direction-icon { transform: rotate(180deg); }
.icon-divider { width: 14px; height: 1px; background: #66dfbd45; }

@keyframes enter-chart {
  from { transform: translateX(-100px); opacity: .4; }
  to { transform: translateX(0); opacity: 1; }
}

@keyframes enter-backtests {
  from { transform: translateX(100px); opacity: .4; }
  to { transform: translateX(0); opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .workspace-screen { animation: none; }
  .workspace-edge-link:hover .workspace-edge-face,
  .workspace-edge-link:focus-visible .workspace-edge-face { transition: none; }
}
</style>
