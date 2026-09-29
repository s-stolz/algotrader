<!-- Throwaway: three navigation layouts on the existing chart/backtest routes via ?variant=A|B|C. -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue';
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
  { key: 'C', name: 'Adjacent screens', note: 'Approach the edge notch to reveal the adjacent workspace.' },
];
const direction = computed(() => isChart.value ? 'from-left' : 'from-right');
const isNearEdge = ref(false);
watch(() => route.fullPath, () => { isNearEdge.value = false; });
function updateEdgeProximity(event: PointerEvent): void {
  if (!enabled.value || variant.value !== 'C' || event.pointerType === 'touch' || event.buttons !== 0) {
    isNearEdge.value = false;
    return;
  }
  const distanceFromEdge = isChart.value ? window.innerWidth - event.clientX : event.clientX;
  const distanceFromCenter = Math.abs(event.clientY - window.innerHeight / 2);
  // A larger exit region prevents flicker while moving onto the revealed button.
  isNearEdge.value = distanceFromEdge < (isNearEdge.value ? 220 : 140) &&
    distanceFromCenter < (isNearEdge.value ? 240 : 180);
}
function navigate(path: string): void {
  void router.push({ path, query: { variant: variant.value } });
}
</script>

<template>
  <div
    :class="enabled ? ['navigation-prototype', `variant-${variant}`] : undefined"
    @pointermove.capture="updateEdgeProximity"
    @pointerleave="isNearEdge = false"
    @pointerdown.capture="isNearEdge = false"
  >
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
        :class="[isChart ? 'edge-right' : 'edge-left', { 'edge-near': isNearEdge }]"
        :aria-label="isChart ? 'Open Backtests' : 'Return to Chart'"
        @click="navigate(isChart ? '/backtests' : '/')"
      >
        <span class="edge-reveal" aria-hidden="true">
          <span class="edge-arrow">{{ isChart ? '→' : '←' }}</span>
          <span>{{ isChart ? 'Backtests' : 'Chart' }}</span>
        </span>
      </button>
    </template>
    <div class="prototype-content" :class="enabled && variant === 'C' ? direction : undefined" :data-screen="isChart ? 'chart' : 'backtests'">
      <nav v-if="enabled && isAnalysis" class="analysis-breadcrumb" aria-label="Backtest location">
        <button @click="navigate('/backtests')">← All backtests</button><span>/ Run analysis</span>
      </nav>
      <slot />
    </div>
    <PrototypeSwitcher v-if="enabled" :variants="variants" :current="variant" :screen="isChart ? 'Chart' : isAnalysis ? 'Run analysis' : 'History'" />
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
.edge-link { position: fixed; top: 50%; transform: translateY(-50%); z-index: 20; width: 24px; height: 120px; padding: 0; background: transparent; border: 0; }
.edge-link::before { content: ''; position: absolute; top: 32px; width: 5px; height: 56px; background: #71879b66; border: 1px solid #96b4c833; box-sizing: border-box; transition: opacity .18s; }
.edge-left { left: 0; }
.edge-right { right: 0; }
.edge-left::before { left: 0; border-radius: 0 5px 5px 0; }
.edge-right::before { right: 0; border-radius: 5px 0 0 5px; }
.edge-reveal { position: absolute; top: 16px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; width: 108px; height: 88px; box-sizing: border-box; background: #1b2b35f5; border: 1px solid #66dfbd60; color: var(--mint); font-size: 12px; box-shadow: 0 6px 24px #0005; opacity: 0; visibility: hidden; transition: transform .2s ease-out, opacity .2s, visibility .2s; }
.edge-left .edge-reveal { left: 0; border-radius: 0 12px 12px 0; transform: translateX(-100%); }
.edge-right .edge-reveal { right: 0; border-radius: 12px 0 0 12px; transform: translateX(100%); }
.edge-near .edge-reveal, .edge-link:hover .edge-reveal, .edge-link:focus-visible .edge-reveal { opacity: 1; visibility: visible; transform: translateX(0); }
.edge-near::before, .edge-link:hover::before, .edge-link:focus-visible::before { opacity: 0; }
.navigation-prototype .edge-link:focus-visible { outline: none; }
.edge-link:focus-visible .edge-reveal { outline: 2px solid var(--mint); outline-offset: -4px; }
.edge-arrow { font-size: 25px; }
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
@media (prefers-reduced-motion: reduce) { .prototype-content { animation: none !important; } .edge-reveal, .edge-link::before { transition: none; } }
@media (max-width: 760px) {
  .navigation-prototype :deep(.workspace-header) { flex-wrap: wrap; }
  .navigation-prototype :deep(.workspace-header > .n-button) { margin-left: auto; }
  .workspace-tabs { padding: 0 12px; } .workspace-tabs .brand { margin-right: 12px; } .brand span, .workspace-hint { display: none; }
  .workspace-tabs button { padding: 0 14px; }
  .workspace-rail { width: 104px; padding: 24px 8px; } .workspace-rail button { flex-direction: column; padding: 10px 3px; font-size: 12px; } .workspace-rail button span { margin: 0; }
  .rail-label, .workspace-rail p { display: none; } .variant-B .prototype-content { margin-left: 100px; }
}
</style>
