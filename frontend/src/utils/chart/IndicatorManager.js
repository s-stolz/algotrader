import { useIndicatorsStore } from "@/stores/indicatorsStore";

export class IndicatorManager {
  constructor(chartManager = null) {
    this.indicatorsStore = useIndicatorsStore();
    this.chartManager = chartManager;
  }

  async addIndicatorSeries(id) {
    const indicator = this.indicatorsStore.getById(id);
    if (!indicator) {
      return;
    }

    const { info, data, paneIndex } = indicator;

    if (!data.length) {
      return;
    }

    for (const outputKey in info.outputs) {
      if (outputKey === 'timestamp') {
        continue;
      }

      const outputInfo = info.outputs[outputKey];
      const transformedData = this.transformIndicatorData(data, outputKey);

      if (transformedData.length > 0) {
        let seriesOptions = { ...outputInfo.plotOptions || {} };
        const seriesKey = `${id}_${outputKey}`;

        this.chartManager.addSeries(
          seriesKey,
          outputInfo.type,
          transformedData,
          seriesOptions,
          paneIndex,
        );
      }
    }
  }

  transformIndicatorData(data, outputKey) {
    return data.map(item => ({
      time: Math.floor(new Date(item.timestamp).getTime() / 1000),
      value: item[outputKey],
    })).filter(item => item.value !== undefined && item.value !== null);
  }

  updateIndicatorStyles(id, outputKey, newStyles) {
    const seriesKey = `${id}_${outputKey}`;
    this.chartManager.updateSeriesOptions(seriesKey, newStyles);
  }

  removeIndicatorSeriesAndData(id) {
    this.removeIndicatorSeries(id);
    this.indicatorsStore.removeIndicator(id);
  }

  refreshIndicatorSeries(id) {
    const indicator = this.indicatorsStore.getById(id);

    if (!indicator) return;

    const { info, data } = indicator;

    for (const outputKey in info.outputs) {
      if (outputKey === 'timestamp') continue;

      const seriesKey = `${id}_${outputKey}`;
      const seriesInfo = this.chartManager.series.get(seriesKey);

      if (!seriesInfo) continue;

      const transformed = this.transformIndicatorData(data, outputKey);
      seriesInfo.series.setData(transformed);
      seriesInfo.data = transformed;
    }
  }

  removeIndicatorSeries(id) {
    const indicator = this.indicatorsStore.getById(id);
    if (!indicator || !this.chartManager) return;

    for (const indicatorOutput in indicator.info.outputs) {
      if (indicatorOutput === 'timestamp') {
        continue;
      }

      const seriesKey = `${id}_${indicatorOutput}`;
      this.chartManager.removeSeries(seriesKey);
    }
  }

  async updateMissingPaneHtmlElements() {
    for (const indicator of this.indicatorsStore.all) {
      if (indicator.paneHtmlElement === null) {
        const paneHtmlElement = await this.chartManager.getPaneHtmlElement(indicator.paneIndex);
        this.indicatorsStore.updateIndicatorPaneElement(indicator._id, paneHtmlElement);
      }
    }
  }

  destroy() {
    const allIndicatorIds = this.indicatorsStore.indicators.keys();

    for (const id of allIndicatorIds) {
      this.removeIndicatorSeriesAndData(id);
    }

    this.indicatorsStore.clear();
  }
}
