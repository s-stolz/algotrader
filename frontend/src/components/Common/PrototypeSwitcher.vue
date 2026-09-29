<script setup lang="ts">
import { onMounted, onUnmounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
const props = defineProps<{ variants: { key: string; name: string; note: string }[]; current: string; screen: string; queryKey?: string }>();
const router = useRouter();
const route = useRoute();
const selected = computed(() => props.variants.find((item) => item.key === props.current)!);
function cycle(offset: number): void {
  const index = props.variants.findIndex((item) => item.key === props.current);
  void router.replace({ path: route.path, query: { ...route.query, [props.queryKey || 'variant']: props.variants[(index + offset + props.variants.length) % props.variants.length].key } });
}
function onKey(event: KeyboardEvent): void {
  const target = event.target as HTMLElement;
  if (target.closest('input, textarea, select, [contenteditable], [role="dialog"], [role="slider"], [role="combobox"]')) return;
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault();
    cycle(event.key === 'ArrowLeft' ? -1 : 1);
  }
}
onMounted(() => window.addEventListener('keydown', onKey));
onUnmounted(() => window.removeEventListener('keydown', onKey));
</script>

<template>
  <aside class="prototype-switcher" aria-label="Navigation prototype variants">
    <div class="switcher-controls">
      <span class="prototype-badge">PROTOTYPE</span>
      <button aria-label="Previous variant" @click="cycle(-1)">←</button>
      <strong aria-live="polite">{{ current }} · {{ selected.name }}</strong>
      <button aria-label="Next variant" @click="cycle(1)">→</button>
    </div>
    <p>{{ selected.note }}</p>
    <small>Screen: {{ screen }} · Create: preview only · History: automatic checks / 5s</small>
  </aside>
</template>

<style scoped>
.prototype-switcher { position: fixed; z-index: 100; bottom: 18px; left: 50%; transform: translateX(-50%); width: max-content; max-width: calc(100vw - 32px); box-sizing: border-box; padding: 10px 20px; border: 1px solid #758499; border-radius: 15px; background: #e1e8f0; color: #182432; box-shadow: 0 12px 50px #0009; text-align: center; }
.switcher-controls { display: flex; align-items: center; justify-content: center; gap: 16px; }
.prototype-badge { font-size: 9px; font-weight: 800; letter-spacing: 1px; border: 1px solid #a4b0be; padding: 4px 6px; border-radius: 4px; }
.switcher-controls button { background: #c8d4e1; border: 0; border-radius: 50%; width: 30px; height: 30px; cursor: pointer; }
.switcher-controls strong { min-width: 205px; font-size: 13px; }
p { font-size: 12px; margin: 5px 0; } small { font-size: 10px; color: #576a7e; }
@media (max-width: 600px) { .prototype-badge { display: none; } .prototype-switcher { width: calc(100vw - 24px); padding: 10px; } p { font-size: 11px; } }
</style>
