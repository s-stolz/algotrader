import { wsService } from "../websocketService";
import { useIndicatorsStore } from "@/stores/indicatorsStore";

export class IndicatorManager {
  constructor(chartManager = null) {
    this.indicatorsStore = useIndicatorsStore();
    this.chartManager = chartManager;

    this.startListening();
  }

  startListening() {
    wsService.on("message", (data) => {
      const message = this.tryParseMessage(data);
      this.handleMessage(message);
    });
  }

  tryParseMessage(data) {
    try {
      return JSON.parse(data);
    } catch (error) {
      console.error("Failed to parse message data:", error);
    }
  }

  handleMessage(message) {
    if (message.type === "indicator-info") {
      this.handleMessageIndicatorInfo(message.data);
    }
  }

  handleMessageIndicatorInfo(messageData) {
    const {
      id: indicatorId,
      indicator_info: indicatorInfo,
      indicator_data: indicatorData,
    } = messageData;
    const indicatorExists = indicatorId !== null;
    let newIndicatorId;

    if (!indicatorExists) {
      newIndicatorId = this.indicatorsStore.addIndicator(
        indicatorInfo,
        indicatorData,
      );
    } else {
      this.indicatorsStore.updateIndicatorData(
        indicatorId,
        indicatorData,
      );
    }

    const id = indicatorId || newIndicatorId;
    this.addIndicatorSeries(id);
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

  removeIndicatorSeries(id) {
    const indicator = this.indicatorsStore.getById(id);
    if (!indicator || !this.chartManager) return;

    for(const indicatorOutput in indicator.info.outputs) {
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
        this.indicatorsStore.updateIndicatorPaneElement(indicator.id, paneHtmlElement);
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
