<!-- Throwaway: three navigation layouts on the existing chart/backtest routes via ?variant=A|B|C. -->
<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import PrototypeSwitcher from '@/components/Common/PrototypeSwitcher.vue';

const route = useRoute();
const router = useRouter();
const enabled = computed(() => import.meta.env.DEV && Boolean(route.query.variant));
const variant = computed(() => ['A', 'B', 'C'].includes(String(route.query.variant)) ? String(route.query.variant) : 'A');
const isChart = computed(() => route.path === '/');
const isAnalysis = computed(() => route.path.startsWith('/backtests/'));
const variants = [
  { key: 'A', name: 'Workspace tabs', note: 'Two visible destinations. Best for frequent switching.' },
  { key: 'B', name: 'Navigation rail', note: 'A permanent home for navigation. Room for more workspaces.' },
  { key: 'C', name: 'Adjacent screens', note: 'Hover inside the button footprint to reveal it; leave to hide.' },
];
const direction = computed(() => isChart.value ? 'from-left' : 'from-right');
const buttonVariant = computed(() => ['1', '2', '3', '4'].includes(String(route.query.button)) ? String(route.query.button) : '1');
const buttonVariants = [
  { key: '1', name: 'Icon spine', note: '44 × 160 · Destination icon and a directional arrow.' },
  { key: '2', name: 'Vertical label', note: '48 × 192 · A readable destination along a narrow tab.' },
  { key: '3', name: 'Screen pair', note: '64 × 176 · Two miniature screens show where you are going.' },
  { key: '4', name: 'Wide icon spine', note: '64 × 176 · Destination icon and a directional arrow.' },
];
function navigate(path: string): void {
  void router.push({ path, query: { ...route.query, variant: variant.value } });
}
</script>

<template>
  <div :class="enabled ? ['navigation-prototype', `variant-${variant}`] : undefined">
    <template v-if="enabled">
      <nav v-if="variant === 'A'" class="workspace-tabs" aria-label="Workspaces">
        <span class="brand">AT<span> / WORKSPACE</span></span>
        <button :aria-current="isChart ? 'page' : undefined" @click="navigate('/')"><span aria-hidden="true">⌁</span> Chart</button>
        <button :aria-current="!isChart ? 'page' : undefined" @click="navigate('/backtests')"><span aria-hidden="true">▤</span> Backtests</button>
        <span class="workspace-hint">Explore. Test. Refine.</span>
      </nav>
      <nav v-else-if="variant === 'B'" class="workspace-rail" aria-label="Workspaces">
        <span class="brand">AT<span> / RESEARCH</span></span>
        <span class="rail-label">WORKSPACES</span>
        <button :aria-current="isChart ? 'page' : undefined" @click="navigate('/')"><span aria-hidden="true">⌁</span> Chart</button>
        <button :aria-current="!isChart ? 'page' : undefined" @click="navigate('/backtests')"><span aria-hidden="true">▤</span> Backtests</button>
        <p>From an idea<br>to evidence.</p>
      </nav>
      <button
        v-else
        :key="isChart ? 'chart-edge' : 'backtests-edge'"
        class="edge-link"
        :class="[isChart ? 'edge-right' : 'edge-left', `edge-design-${buttonVariant}`]"
        :aria-label="isChart ? 'Open Backtests' : 'Return to Chart'"
        @click="navigate(isChart ? '/backtests' : '/')"
      >
        <span class="edge-reveal" aria-hidden="true">
          <template v-if="buttonVariant !== '3'">
            <svg class="destination-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path v-if="isChart" d="M9 3h6M10 3v6L4 19a1.3 1.3 0 0 0 1.2 2h13.6a1.3 1.3 0 0 0 1.2-2L14 9V3M8 14h8M10 17h.01M14 19h.01" />
              <path v-else d="M3 3v18h18M7 15l4-5 4 3 6-8" />
            </svg>
            <span v-if="buttonVariant === '2'" class="vertical-label">{{ isChart ? 'Backtests' : 'Chart' }}</span>
            <span v-else class="icon-divider" />
            <svg class="direction-icon" :class="{ reverse: !isChart }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6" /></svg>
          </template>
          <template v-else>
            <span class="mini-screen" :class="{ destination: !isChart }">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="m3 17 5-7 5 3 8-8M3 21h18" /></svg>
            </span>
            <svg class="direction-icon" :class="{ reverse: !isChart }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h16m-6-6 6 6-6 6" /></svg>
            <span class="mini-screen" :class="{ destination: isChart }">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 5h16M4 11h6m4 0h6M4 17h6m4 0h6" /></svg>
            </span>
            <span class="screen-dots"><i :class="{ current: isChart }" /><i :class="{ current: !isChart }" /></span>
          </template>
        </span>
      </button>
    </template>
    <div class="prototype-content" :class="enabled && variant === 'C' ? direction : undefined" :data-screen="isChart ? 'chart' : 'backtests'">
      <nav v-if="enabled && isAnalysis" class="analysis-breadcrumb" aria-label="Backtest location">
        <button @click="navigate('/backtests')">← All backtests</button><span>/ Run analysis</span>
      </nav>
      <slot />
    </div>
    <PrototypeSwitcher v-if="enabled" :variants="variant === 'C' ? buttonVariants : variants" :current="variant === 'C' ? buttonVariant : variant" :query-key="variant === 'C' ? 'button' : 'variant'" :screen="isChart ? 'Chart' : isAnalysis ? 'Run analysis' : 'History'" />
  </div>
</template>

<style scoped>
.navigation-prototype, .navigation-prototype :deep(*) { font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
.navigation-prototype { --mint: #66dfbd; min-height: calc(100vh - 20px); padding-bottom: 116px; color: #dce4ed; }
.navigation-prototype button { cursor: pointer; color: inherit; font: inherit; }
.navigation-prototype button:focus-visible { outline: 2px solid var(--mint); outline-offset: 5px; }
.navigation-prototype :deep([data-testid="open-backtest-runs"]) { display: none; }
.brand { font-size: 19px; font-weight: 700; letter-spacing: 2px; color: var(--mint); white-space: nowrap; }
.brand span { font-size: 10px; color: #7f8fa0; letter-spacing: 1.5px; }
.workspace-tabs { display: flex; align-items: center; gap: 6px; padding: 0 26px; height: 66px; border-bottom: 1px solid #293442; margin: -10px -10px 22px; background: #151c26; }
.workspace-tabs .brand { margin-right: 38px; }
.workspace-tabs button { background: none; border: 0; border-bottom: 2px solid transparent; align-self: stretch; padding: 0 24px; color: #95a3b3; }
.workspace-tabs button[aria-current] { border-bottom-color: var(--mint); color: var(--mint); background: #65dfbd09; }
.workspace-tabs button span, .workspace-rail button span { margin-right: 9px; font-size: 19px; }
.workspace-hint { margin-left: auto; font-size: 12px; color: #657688; }
.workspace-rail { position: fixed; inset: 0 auto 0 0; width: 192px; padding: 30px 16px; box-sizing: border-box; background: #171e28; border-right: 1px solid #2a3441; display: flex; flex-direction: column; gap: 8px; }
.workspace-rail .brand { margin: 0 8px 45px; }
.rail-label { font-size: 10px; letter-spacing: 1.6px; color: #7d8a9c; margin: 0 12px 10px; }
.workspace-rail button { display: flex; align-items: center; border: 1px solid transparent; background: transparent; padding: 13px 12px; text-align: left; border-radius: 7px; color: #96a4b4; }
.workspace-rail button[aria-current] { color: var(--mint); border-color: #66dfbd35; background: #66dfbd0b; }
.workspace-rail p { margin: auto 12px 10px; color: #607184; line-height: 1.7; font-size: 12px; }
.variant-B .prototype-content { margin-left: 196px; padding-top: 8px; }
.variant-C { color-scheme: dark; position: fixed; inset: 0; box-sizing: border-box; min-height: 0; padding: 10px; overflow: hidden; }
.variant-C .prototype-content { height: 100%; min-height: 0; margin: 0; overflow-x: hidden; overflow-y: auto; }
.variant-C .prototype-content[data-screen='chart'] { overflow: hidden; }
.variant-C [data-screen='chart'] > :deep(div) { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.variant-C [data-screen='chart'] :deep(#wrapper-select) { flex-shrink: 0; }
.edge-link { position: fixed; top: 50%; transform: translateY(-50%); z-index: 20; width: var(--edge-width); height: var(--edge-height); padding: 0; background: transparent; border: 0; }
.edge-design-1 { --edge-width: 44px; --edge-height: 160px; --edge-radius: 22px; }
.edge-design-2 { --edge-width: 48px; --edge-height: 192px; --edge-radius: 9px; }
.edge-design-3, .edge-design-4 { --edge-width: 64px; --edge-height: 176px; --edge-radius: 16px; }
.edge-link::before { content: ''; position: absolute; top: 0; bottom: 0; width: 5px; background: #71879b66; border: 1px solid #96b4c833; box-sizing: border-box; }
.edge-left { left: 0; }
.edge-right { right: 0; }
.edge-left::before { left: 0; border-radius: 0 5px 5px 0; }
.edge-right::before { right: 0; border-radius: 5px 0 0 5px; }
.edge-reveal { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 20px; box-sizing: border-box; background: #1b2b35fa; border: 1px solid #66dfbd60; color: var(--mint); opacity: 0; visibility: hidden; pointer-events: none; }
.edge-left .edge-reveal { border-radius: 0 var(--edge-radius) var(--edge-radius) 0; transform: translateX(-100%); }
.edge-right .edge-reveal { border-radius: var(--edge-radius) 0 0 var(--edge-radius); transform: translateX(100%); }
.edge-link:hover .edge-reveal, .edge-link:focus-visible .edge-reveal { opacity: 1; visibility: visible; transform: translateX(0); transition: transform .14s ease-out, opacity .14s; }
.edge-link:hover::before, .edge-link:focus-visible::before { opacity: 0; }
.navigation-prototype .edge-link:focus-visible { outline: none; }
.edge-link:focus-visible .edge-reveal { outline: 2px solid var(--mint); outline-offset: -4px; }
.destination-icon { width: 23px; height: 23px; }
.direction-icon { width: 21px; height: 21px; }
.direction-icon.reverse { transform: rotate(180deg); }
.icon-divider { width: 14px; height: 1px; background: #66dfbd45; }
.edge-design-2 .edge-reveal { gap: 14px; background: #19252f; }
.edge-design-2 .destination-icon { width: 19px; height: 19px; }
.vertical-label { writing-mode: vertical-rl; font-size: 12px; letter-spacing: 1.4px; color: #d6e5e9; }
.edge-design-3 .edge-reveal { gap: 10px; background: #18222e; }
.mini-screen { display: flex; align-items: center; justify-content: center; width: 34px; height: 30px; border: 1px solid #526273; border-radius: 4px; color: #8393a3; }
.mini-screen svg { width: 21px; height: 21px; }
.mini-screen.destination { border-color: #66dfbd99; color: var(--mint); background: #66dfbd10; }
.screen-dots { display: flex; gap: 5px; margin-top: 3px; }
.screen-dots i { width: 4px; height: 4px; border-radius: 50%; background: #526273; }
.screen-dots .current { background: var(--mint); }
.variant-C .from-left { animation: arrive-left .32s ease-out; }
.variant-C .from-right { animation: arrive-right .32s ease-out; }
.analysis-breadcrumb { display: flex; align-items: center; gap: 14px; font-size: 12px; color: #8291a2; padding: 0 28px 16px; }
.analysis-breadcrumb button { background: transparent; border: none; padding: 6px 0; color: var(--mint); }
.navigation-prototype :deep(.workspace-header) { flex-direction: row; align-items: center; }
.navigation-prototype :deep(.workspace-header > .n-button) { flex-shrink: 0; }
.navigation-prototype :deep(#chart-area) { height: calc(100vh - 230px); }
.variant-C [data-screen='chart'] :deep(#chart-area) { flex: 1; min-height: 0; height: auto; }
@keyframes arrive-left { from { opacity: .4; transform: translateX(-100px); } to { opacity: 1; transform: translateX(0); } }
@keyframes arrive-right { from { opacity: .4; transform: translateX(100px); } to { opacity: 1; transform: translateX(0); } }
@media (prefers-reduced-motion: reduce) { .prototype-content { animation: none !important; } .edge-link:hover .edge-reveal, .edge-link:focus-visible .edge-reveal { transition: none; } }
@media (max-width: 760px) {
  .navigation-prototype :deep(.workspace-header) { flex-wrap: wrap; }
  .navigation-prototype :deep(.workspace-header > .n-button) { margin-left: auto; }
  .workspace-tabs { padding: 0 12px; } .workspace-tabs .brand { margin-right: 12px; } .brand span, .workspace-hint { display: none; }
  .workspace-tabs button { padding: 0 14px; }
  .workspace-rail { width: 104px; padding: 24px 8px; } .workspace-rail button { flex-direction: column; padding: 10px 3px; font-size: 12px; } .workspace-rail button span { margin: 0; }
  .rail-label, .workspace-rail p { display: none; } .variant-B .prototype-content { margin-left: 100px; }
}
</style>
