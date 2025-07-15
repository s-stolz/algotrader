import {
  createChart,
  LineSeries,
  AreaSeries,
  BarSeries,
  BaselineSeries,
  CandlestickSeries,
  HistogramSeries,
} from 'lightweight-charts';

export class ChartManager {
  constructor(options = {}) {
    this.chart = null;
    this.series = new Map();
    this.container = null;
    this.loadedBars = 5000;

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
      autoSize: true,
      ...options
    };

    this.timeScaleOptions = {
      timeVisible: true,
      secondsVisible: false,
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
      this.removeSeries(key);
    }

    const newSeries = this.createSeries(type, seriesOptions, paneIndex);

    if (newSeries) {
      newSeries.setData(data);
      this.series.set(key, {
        series: newSeries,
        type,
        data: [...data],
        options: { ...seriesOptions }
      });
    }

    return newSeries;
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

  updateSeriesData(key, data) {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo) {
      console.error(`Series '${key}' not found`);
      return false;
    }

    try {
      const slicedData = this.sliceData(data);
      seriesInfo.series.setData(slicedData);
      seriesInfo.data = [...data];
      return true;
    } catch (error) {
      console.error(`Failed to update series '${key}':`, error);
      return false;
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

  updateSeriesOptions(key, newOptions) {
    const seriesInfo = this.series.get(key);
    if (!seriesInfo) {
      console.error(`Series '${key}' not found`);
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

  sliceData(data) {
    const len = data.length;
    const start = Math.max(0, len - this.loadedBars);
    return data.slice(start, len);
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
