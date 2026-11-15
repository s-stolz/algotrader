<script lang="ts">
import { lazyComponent } from '@/components/Common/lazyComponent';
export default lazyComponent(() => import('./ChartView.vue'), 'Chart');
</script>
