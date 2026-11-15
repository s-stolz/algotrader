import { describe, expect, it } from 'vitest';
import { runtimeImports, staticModules } from '../sourceImports';

describe('workspace loading boundaries', () => {
  it('imports individual icons rather than entire icon catalogs', () => {
    const modules = new Set([
      ...staticModules('src/main.ts'),
      ...staticModules('src/views/ChartView.vue'),
      ...staticModules('src/views/BacktestWorkspaceView.vue'),
    ]);
    for (const file of modules) {
      expect(runtimeImports(file), file).not.toContain('@/icons');
      expect(runtimeImports(file), file).not.toContain('@vicons/ionicons5');
    }
  });
  it('keeps both workspace implementations out of application startup', () => {
    const modules = staticModules('src/main.ts');
    for (const file of [
      'src/views/ChartView.vue',
      'src/views/BacktestWorkspaceView.vue',
      'src/utils/chart/ChartManager.ts',
      'src/stores/indicatorsStore.ts',
      'src/views/BacktestCreationDrawer.vue',
    ])
      expect(modules.has(file), file).toBe(false);
  });
  it('loads chart dialogs only when requested', () => {
    const modules = staticModules('src/views/ChartView.vue');
    for (const file of [
      'SymbolSearchModal.vue',
      'IndicatorSearchModal.vue',
      'SymbolFormModal.vue',
      'RemoveMarketModal.vue',
      'Upload/UploadDataModal.vue',
    ])
      expect(modules.has(`src/components/TopBar/Modals/${file}`), file).toBe(
        false,
      );
    expect(modules.has('src/views/BacktestWorkspaceView.vue')).toBe(false);
    expect(modules.has('src/api/backtesterClient.ts')).toBe(false);
    expect(modules.has('src/api/equityReplayStream.ts')).toBe(false);
  });
  it('keeps creation, inspection and visualization code out of backtest history', () => {
    const modules = staticModules('src/views/BacktestWorkspaceView.vue');
    for (const file of [
      'src/views/BacktestCreationDrawer.vue',
      'src/views/workspace/BacktestInspection.vue',
      'src/views/workspace/heatmap/HeatmapPlot.vue',
      'src/views/EquityReplayCharts.vue',
      'src/utils/chart/ChartManager.ts',
      'src/stores/indicatorsStore.ts',
    ])
      expect(modules.has(file), file).toBe(false);
  });
});
