import { wsService } from "@/utils/websocketService";
import { defineStore } from "pinia";
import { markRaw } from "vue";

const INITIAL_INDICATOR_LIMIT = 500;

export const useIndicatorsStore = defineStore('indicators', {
  state: () => ({
    indicators: new Map(),
    paneCount: 1,
    liveSubscriptions: new Map(),
  }),

  getters: {
    all: (state) => Array.from(state.indicators.values()),
    getById: (state) => (_id) => state.indicators.get(_id),
    exists: (state) => (_id) => state.indicators.has(_id),
  },

  actions: {
    resetHistoryFlags() {
      for (const indicator of this.all) {
        indicator.hasExpandedHistory = false;
        indicator.currentLimit = INITIAL_INDICATOR_LIMIT;
      }
    },

    requestAllIndicators(symbol, timeframe, exchange = null) {
      for (const indicator of this.all) {
        if (indicator.hasExpandedHistory) continue;

        const queryParams = {
          symbol: symbol,
          timeframe: timeframe,
          limit: indicator.currentLimit || INITIAL_INDICATOR_LIMIT,
        };
        if (exchange) {
          queryParams.exchange = exchange;
        }

        const body = {
          parameters: this.extractParameterValues(indicator.parameters),
        };

        this.requestIndicator(indicator._id, indicator.indicatorId, queryParams, body);
      }
    },

    async fetchOlderForAll(symbol, timeframe, exchange = null, batchSize = 5000) {
      for (const indicator of this.all) {
        if (!indicator.data.length) continue;
        indicator.hasExpandedHistory = true;

        const earliestTs = indicator.data[0].timestamp_ms;
        const queryParams = { symbol: symbol, timeframe, end_ms: earliestTs, limit: batchSize };
        if (exchange) {
          queryParams.exchange = exchange;
        }
        const body = { parameters: this.extractParameterValues(indicator.parameters) };

        await this.requestIndicatorPrepend(indicator._id, indicator.indicatorId, queryParams, body);
      }
    },

    async requestIndicator(_id, indicatorId, query, body = {}) {
      const params = new URLSearchParams(query).toString();

      if (_id && this.liveSubscriptions.has(_id)) {
        await this.unsubscribeIndicatorLive(_id);
      }

      try {
        const response = await fetch(`/api/indicator-api/indicators/${indicatorId}?${params}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(body),
        });

        const { data } = await response.json();

        const localId = this.handleMessageIndicatorInfo({
          _id,
          indicatorId,
          ...data,
        });

        const activeId = localId || _id;
        const indicator = this.indicators.get(activeId);

        if (indicator && query.symbol && query.timeframe) {
          await this.subscribeIndicatorLive(activeId, {
            symbol: query.symbol,
            timeframe: query.timeframe,
            exchange: query.exchange || null,
            indicatorId: indicator.indicatorId,
            parameters: this.extractParameterValues(indicator.parameters),
          });
        }

        return activeId;
      } catch (error) {
        console.error("Error fetching indicator:", error);
        return null;
      }
    },

    async requestIndicatorPrepend(_id, indicatorId, query, body = {}) {
      const indicator = this.indicators.get(_id);

      if (!indicator || !indicator.data.length) return;

      const params = new URLSearchParams(query).toString();

      try {
        const response = await fetch(`/api/indicator-api/indicators/${indicatorId}?${params}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });

        const data = await response.json();

        const { indicator_data: newData } = data.data;

        const mergedData = [...newData, ...indicator.data];
        this.updateIndicatorData(_id, mergedData);
      } catch (error) {
        console.error('Failed to prepend indicator data', error);
      }
    },

    handleMessageIndicatorInfo(indicatorResponse) {
      const {
        _id,
        indicatorId,
        indicator_info: indicatorInfo,
        indicator_data: indicatorData,
      } = indicatorResponse;
      const isNewIndicatorRequest = _id === null || _id === undefined;
      let newLocalId = _id;

      if (isNewIndicatorRequest) {
        newLocalId = this.addIndicator(
          indicatorInfo,
          indicatorData,
          indicatorId,
        );
      } else {
        if (!this.indicators.has(_id)) {
          return null;
        }

        this.updateIndicatorData(_id, indicatorData);
      }

      return newLocalId;
    },

    addIndicator(info, data, indicatorId, providedParameters = {}) {
      const _id = String(Date.now());
      let finalParameters = { ...providedParameters };

      for (const [key, paramInfo] of Object.entries(info.parameters)) {
        if (!(key in finalParameters)) {
          finalParameters[key] = {
            ...paramInfo,
            value: paramInfo.default,
          };
        } else if (!('value' in finalParameters[key])) {
          finalParameters[key].value = paramInfo.default;
        }
      }

      const indicator = {
        _id,
        indicatorId,
        info: { ...info },
        paneIndex: info.overlay ? 0 : this.paneCount++,
        paneHtmlElement: null,
        data: markRaw([...data]),
        lastLivePoint: null,
        dataVersion: 0,
        parameters: finalParameters,
        styles: this.createStyles(info.outputs || {}),
        currentLimit: data.length || INITIAL_INDICATOR_LIMIT,
        hasExpandedHistory: false,
      };
      this.indicators.set(_id, indicator);

      return _id;
    },

    updateIndicatorData(_id, newData) {
      const indicator = this.indicators.get(_id);

      if (!indicator) return;

      indicator.data = markRaw(Array.isArray(newData) ? [...newData] : []);
      indicator.currentLimit = indicator.data.length;
      indicator.lastLivePoint = indicator.data.length ? indicator.data[indicator.data.length - 1] : null;
      indicator.dataVersion = (indicator.dataVersion || 0) + 1;
    },

    handleLiveUpdate(message) {
      if (!message || message.type !== 'indicatorUpdate') return null;

      const _id = message.clientIndicatorId;
      const indicator = this.indicators.get(_id);
      if (!indicator) return null;

      const timestampMs = Number(message.timestamp_ms);
      if (!Number.isFinite(timestampMs)) return null;

      const values = message.values && typeof message.values === 'object' ? message.values : {};
      const point = { timestamp_ms: timestampMs, ...values };

      const lastLivePoint = indicator.lastLivePoint;
      if (!lastLivePoint) {
        indicator.lastLivePoint = point;
        return point;
      }

      if (Number(lastLivePoint.timestamp_ms) === timestampMs) {
        const merged = { ...lastLivePoint, ...point };
        indicator.lastLivePoint = merged;
        return merged;
      }

      if (Number(lastLivePoint.timestamp_ms) < timestampMs) {
        indicator.lastLivePoint = point;
        return point;
      }

      return null;
    },

    async subscribeIndicatorLive(_id, { symbol, timeframe, exchange = null, indicatorId, parameters = {} }) {
      if (!_id || !symbol || !timeframe || indicatorId === null || indicatorId === undefined) return;

      const payload = {
        symbol,
        timeframe,
        exchange,
        indicatorId,
        parameters,
        clientIndicatorId: _id,
      };

      this.liveSubscriptions.set(_id, payload);
      try {
        await wsService.send('subscribeIndicator', payload);
      } catch (error) {
        console.error('Failed to subscribe indicator stream:', error);
      }
    },

    async unsubscribeIndicatorLive(_id) {
      const payload = this.liveSubscriptions.get(_id);
      if (!payload) return;

      try {
        await wsService.send('unsubscribeIndicator', payload);
      } catch (error) {
        console.error('Failed to unsubscribe indicator stream:', error);
      } finally {
        this.liveSubscriptions.delete(_id);
      }
    },

    async unsubscribeAllLive() {
      const subscriptions = Array.from(this.liveSubscriptions.entries());
      for (const [id, payload] of subscriptions) {
        try {
          await wsService.send('unsubscribeIndicator', payload);
        } catch (error) {
          console.error('Failed to unsubscribe indicator stream:', error);
        } finally {
          this.liveSubscriptions.delete(id);
        }
      }
    },

    async resubscribeAllLive(symbol, timeframe, exchange = null) {
      await this.unsubscribeAllLive();
      for (const indicator of this.all) {
        await this.subscribeIndicatorLive(indicator._id, {
          symbol,
          timeframe,
          exchange,
          indicatorId: indicator.indicatorId,
          parameters: this.extractParameterValues(indicator.parameters),
        });
      }
    },

    updateIndicatorParameters(_id, newParameters) {
      const indicator = this.indicators.get(_id);

      for (const [key, paramVal] of Object.entries(newParameters)) {
        if (!indicator.parameters[key]) continue;
        if (paramVal && typeof paramVal === 'object' && 'value' in paramVal) {
          indicator.parameters[key].value = paramVal.value;
        } else {
          indicator.parameters[key].value = paramVal;
        }
      }

      return indicator.parameters;
    },

    removeIndicator(_id) {
      const indicator = this.indicators.get(_id);
      if (!indicator) return;

      this.unsubscribeIndicatorLive(_id);

      const paneIndex = indicator.paneIndex;
      if (paneIndex > 0) {
        this.updateIndicatorsPaneIndex(paneIndex);
      }

      this.indicators.delete(_id);
    },

    updateIndicatorsPaneIndex(changedPaneIndex) {
      for (const [_, indicator] of this.indicators.entries()) {
        if (indicator.paneIndex > changedPaneIndex) {
          indicator.paneIndex--;
          indicator.paneHtmlElement = null;
        }
      }

      this.paneCount = Math.max(1, this.paneCount - 1);
    },

    updateIndicatorPaneElement(_id, paneHtmlElement) {
      const indicator = this.indicators.get(_id);
      indicator.paneHtmlElement = paneHtmlElement;
    },

    clear() {
      void this.unsubscribeAllLive();
      this.indicators.clear();
      this.paneCount = 1;
    },

    extractParameterValues(parameters) {
      const out = {};
      for (const [k, v] of Object.entries(parameters)) {
        out[k] = v.value !== undefined ? v.value : v.default;
      }
      return out;
    },

    createStyles(outputs) {
      const styles = {};

      for (const outputKey in outputs) {
        if (outputKey !== 'timestamp') {
          styles[outputKey] = {
            ...outputs[outputKey].plotOptions || {},
          };
        }
      }
      return styles;
    },
  },
});
