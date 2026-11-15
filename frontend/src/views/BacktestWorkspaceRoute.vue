<script lang="ts">
import { lazyComponent } from '@/components/Common/lazyComponent';
export default lazyComponent(
  () => import('./BacktestWorkspaceView.vue'),
  'Backtests',
);
</script>
