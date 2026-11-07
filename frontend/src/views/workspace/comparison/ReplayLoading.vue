<template>
  <div
    aria-busy="true"
    class="replay-loading"
  >
    <p role="status"
      >Loading equity and drawdown · {{ count }}
      {{ count === 1 ? 'run' : 'runs' }}</p
    >
    <template v-if="showSkeleton">
      <section
        v-for="label in ['Equity', 'Drawdown']"
        :key="label"
        :aria-label="`${label} loading`"
      >
        <h3>{{ label }}</h3>
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
defineProps<{ count: number; showSkeleton: boolean }>();
</script>
<style scoped>
p {
  color: var(--design-color-muted);
}
h3 {
  font-size: var(--design-text-body);
  font-weight: 500;
}
.chart-skeleton {
  position: relative;
  height: 240px;
  overflow: hidden;
  border-bottom: 1px solid var(--design-color-border);
  border-left: 1px solid var(--design-color-border);
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
