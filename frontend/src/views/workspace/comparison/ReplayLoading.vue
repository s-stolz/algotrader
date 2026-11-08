<template>
  <div
    aria-busy="true"
    class="replay-loading"
  >
    <template v-if="showSkeleton">
      <section
        v-for="label in ['Equity', 'Drawdown']"
        :key="label"
        :aria-label="`${label} loading`"
      >
        <h2>{{ label }}</h2>
        <div
          class="chart-skeleton"
          aria-hidden="true"
          ><span
        /></div>
      </section>
    </template>
  </div>
</template>
<script setup lang="ts">
defineProps<{ showSkeleton: boolean }>();
</script>
<style scoped>
.replay-loading {
  display: grid;
  gap: var(--design-space-xl);
}
h2 {
  font-size: var(--design-text-heading);
  margin: 0 0 var(--design-space-md);
}
.chart-skeleton {
  position: relative;
  height: 240px;
  overflow: hidden;
  border: 1px solid var(--design-color-border);
  border-radius: var(--design-radius-panel);
  background: repeating-linear-gradient(
    to bottom,
    transparent 0,
    transparent 59px,
    var(--design-color-border) 60px
  );
}
.chart-skeleton span {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent,
    var(--design-color-inset),
    transparent
  );
  animation: loading 1.8s ease-in-out infinite;
}
@keyframes loading {
  from {
    transform: translateX(-100%);
  }
  to {
    transform: translateX(100%);
  }
}
@media (prefers-reduced-motion: reduce) {
  .chart-skeleton span {
    animation: none;
  }
}
</style>
