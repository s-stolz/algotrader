import {
  AreaSeries,
  BarSeries,
  BaselineSeries,
  CandlestickSeries,
  createChart,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
} from 'lightweight-charts';

export class ChartManager {
  constructor(options = {}) {
    this.chart = null;
    this.series = new Map();
    this.container = null;
    this.loadedBars = 500;
    this.initialVisibleCandles = 50;

    this.defaultOptions = {
      layout: {
        textColor: '#d1d4dc',
        background: { type: 'solid', color: 'transparent' },
        panes: {
          separatorColor: 'rgba(96,96,96,0.3)',
        },
      },
      grid: {
        vertLines: { color: 'transparent' },
        horzLines: { color: 'transparent' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      autoSize: true,
      ...options,
    };

    this.timeScaleOptions = {
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 5,
    };

    this.seriesTypes = {
      line: LineSeries,
      area: AreaSeries,
      bar: BarSeries,
      baseline: BaselineSeries,
      candlestick: CandlestickSeries,
      histogram: HistogramSeries,
    };
  }

  init(containerElement) {
    this.container = containerElement;

    try {
      this.chart = createChart(containerElement, this.defaultOptions);
      this.chart.timeScale().applyOptions(this.timeScaleOptions);
    } catch (error) {
      console.error('Failed to initialize chart:', error);
    }
  }

  addSeries(key, type, data, seriesOptions = {}, paneIndex = 0) {
    if (!this.chart) {
      console.error('Chart not initialized');
      return null;
    }

    if (this.series.has(key)) {
      const existingSeriesInfo = this.series.get(key);

      existingSeriesInfo.series.setData(data);
      existingSeriesInfo.data = [...data];

      if (JSON.stringify(existingSeriesInfo.options) !== JSON.stringify(seriesOptions)) {
        existingSeriesInfo.series.applyOptions(seriesOptions);
        existingSeriesInfo.options = { ...seriesOptions };
      }

      return existingSeriesInfo.series;
    }

    const newSeries = this.createSeries(type, seriesOptions, paneIndex);

    if (newSeries) {
      newSeries.setData(data);
      this.series.set(key, {
        series: newSeries,
        type,
        data: [...data],
        options: { ...seriesOptions },
      });
    }

    return newSeries;
  }

  updateCandle(key, candle) {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo) {
      console.warn(`Series '${key}' not found`);
      return;
    }

    try {
      const last = seriesInfo.data[seriesInfo.data.length - 1];

      if (last.time === candle.time) {
        seriesInfo.series.update(candle);
        seriesInfo.data[seriesInfo.data.length - 1] = candle;
        return;
      }

      if (last.time < candle.time) {
        seriesInfo.series.update(candle);
        seriesInfo.data.push(candle);
        return;
      }
    } catch (error) {
      console.error(`Failed to update candle for series '${key}':`, error);
    }
  }

  updateSeriesPoint(key, point) {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo) {
      return;
    }

    try {
      const last = seriesInfo.data[seriesInfo.data.length - 1];
      if (last.time === point.time) {
        if (last.value === point.value) {
          return;
        }
        seriesInfo.series.update(point);
        seriesInfo.data[seriesInfo.data.length - 1] = point;
        return;
      }

      if (last.time < point.time) {
        seriesInfo.series.update(point);
        seriesInfo.data.push(point);
        return;
      }
    } catch (error) {
      console.error(`Failed to update point for series '${key}':`, error);
    }
  }

  createSeries(type, seriesOptions = {}, paneIndex) {
    if (!this.chart) {
      console.error('Chart not initialized');
      return null;
    }

    const SeriesConstructor = this.seriesTypes[type];
    if (!SeriesConstructor) {
      console.error('Invalid series type:', type);
      return null;
    }

    try {
      const newSeries = this.chart.addSeries(SeriesConstructor, seriesOptions, paneIndex);
      return newSeries;
    } catch (error) {
      console.error('Failed to create series:', error);
      return null;
    }
  }

  removeSeries(key) {
    const seriesInfo = this.series.get(key);

    try {
      this.chart.removeSeries(seriesInfo.series);
      this.series.delete(key);
    } catch (error) {
      console.error(`Failed to remove series '${key}':`, error);
    }
  }

  scrollToRealTime() {
    if (!this.chart) return;

    const ohlcSeriesInfo = this.series.get('ohlc');
    const candleCount = ohlcSeriesInfo?.data?.length || 0;

    if (candleCount > 0) {
      const to = candleCount - 1;
      const from = Math.max(0, to - this.initialVisibleCandles + 1);
      this.chart.timeScale().setVisibleLogicalRange({ from, to });
    }

    this.chart.timeScale().scrollToRealTime();
  }

  updateSeriesOptions(key, newOptions) {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo) {
      return false;
    }
    try {
      seriesInfo.series.applyOptions(newOptions);
      seriesInfo.options = { ...seriesInfo.options, ...newOptions };
      return true;
    } catch (error) {
      console.error(`Failed to update options for series '${key}':`, error);
      return false;
    }
  }

  async getPaneHtmlElement(paneIndex = 0) {
    if (!this.isValidPaneIndex(paneIndex)) {
      return null;
    }

    const pane = this.chart.panes()[paneIndex];
    return await this.waitForPaneHtmlElement(pane);
  }

  isValidPaneIndex(paneIndex) {
    const panes = this.chart.panes();
    const isValid = paneIndex >= 0 && paneIndex < panes.length;

    if (!isValid) {
      console.error(`Invalid pane index: ${paneIndex}. Available panes: ${panes.length}`);
    }

    return isValid;
  }

  async waitForPaneHtmlElement(pane, maxAttempts = 10, delay = 100) {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const element = this.tryGetHtmlElement(pane);
      if (element) {
        return element;
      }

      if (attempt < maxAttempts - 1) {
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }

    console.warn('Pane HTML element not available after maximum attempts');
    return null;
  }

  tryGetHtmlElement(pane) {
    try {
      return pane?.getHTMLElement?.() || null;
    } catch {
      return null;
    }
  }

  subscribeCrosshairMove(callback) {
    if (this.chart) {
      this.chart.subscribeCrosshairMove(callback);
    }
  }

  subscribeVisibleLogicalRangeChange(callback) {
    if (this.chart) {
      this.chart.timeScale().subscribeVisibleLogicalRangeChange(callback);
    }
  }

  destroy() {
    if (this.chart) {
      this.series.forEach((_, key) => {
        this.removeSeries(key);
      });

      this.chart.remove();
      this.chart = null;
      this.container = null;
    }
  }
}
