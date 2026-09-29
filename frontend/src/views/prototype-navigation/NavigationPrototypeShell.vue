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
  { key: 'C', name: 'Adjacent screens', note: 'Chart on the left, backtests on the right. Click the edge to slide.' },
];
const direction = computed(() => isChart.value ? 'from-left' : 'from-right');
function navigate(path: string): void {
  void router.push({ path, query: { variant: variant.value } });
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
      <template v-else>
        <nav class="spatial-map" aria-label="Workspaces">
          <button :aria-current="isChart ? 'page' : undefined" @click="navigate('/')">01 · Chart</button>
          <span aria-hidden="true">—</span>
          <button :aria-current="!isChart ? 'page' : undefined" @click="navigate('/backtests')">02 · Backtests</button>
        </nav>
        <button class="edge-link" :class="isChart ? 'edge-right' : 'edge-left'" @click="navigate(isChart ? '/backtests' : '/')">
          <span class="edge-arrow" aria-hidden="true">{{ isChart ? '→' : '←' }}</span>
          <span>{{ isChart ? 'Backtests' : 'Chart' }}</span>
        </button>
      </template>
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
.spatial-map { display: flex; align-items: center; justify-content: center; gap: 18px; margin: 8px auto 18px; color: #617184; }
.spatial-map button { background: transparent; border: none; padding: 10px; color: #8392a4; font-size: 12px; }
.spatial-map button[aria-current] { color: var(--mint); }
.variant-C .prototype-content { margin: 0 80px; }
.edge-link { position: fixed; top: 43%; z-index: 20; display: flex; align-items: center; flex-direction: column; gap: 9px; width: 80px; padding: 24px 4px; background: #1a2533; border: 1px solid #3c5363; font-size: 11px !important; transition: background .18s, width .18s; }
.edge-left { left: 0; border-radius: 0 14px 14px 0; }
.edge-right { right: 0; border-radius: 14px 0 0 14px; }
.edge-link:hover { background: #234039; width: 90px; color: var(--mint); }
.edge-arrow { font-size: 25px; }
.variant-C .from-left { animation: arrive-left .32s ease-out; }
.variant-C .from-right { animation: arrive-right .32s ease-out; }
.analysis-breadcrumb { display: flex; align-items: center; gap: 14px; font-size: 12px; color: #8291a2; padding: 0 28px 16px; }
.analysis-breadcrumb button { background: transparent; border: none; padding: 6px 0; color: var(--mint); }
.navigation-prototype :deep(.workspace-header) { flex-direction: row; align-items: center; }
.navigation-prototype :deep(.workspace-header > .n-button) { flex-shrink: 0; }
.navigation-prototype :deep(#chart-area) { height: calc(100vh - 230px); }
@keyframes arrive-left { from { opacity: .4; transform: translateX(-100px); } to { opacity: 1; transform: translateX(0); } }
@keyframes arrive-right { from { opacity: .4; transform: translateX(100px); } to { opacity: 1; transform: translateX(0); } }
@media (prefers-reduced-motion: reduce) { .prototype-content { animation: none !important; } .edge-link { transition: none; } }
@media (max-width: 760px) {
  .navigation-prototype :deep(.workspace-header) { flex-wrap: wrap; }
  .navigation-prototype :deep(.workspace-header > .n-button) { margin-left: auto; }
  .workspace-tabs { padding: 0 12px; } .workspace-tabs .brand { margin-right: 12px; } .brand span, .workspace-hint { display: none; }
  .workspace-tabs button { padding: 0 14px; }
  .workspace-rail { width: 104px; padding: 24px 8px; } .workspace-rail button { flex-direction: column; padding: 10px 3px; font-size: 12px; } .workspace-rail button span { margin: 0; }
  .rail-label, .workspace-rail p { display: none; } .variant-B .prototype-content { margin-left: 100px; }
  .variant-C .prototype-content { margin: 0 34px; } .edge-link { width: 40px; font-size: 9px !important; padding: 18px 1px; } .edge-link:hover { width: 44px; }
}
</style>
