import { defineStore } from "pinia";

export const useIndicatorsStore = defineStore('indicators', {
  state: () => ({
    indicators: new Map(),
    paneCount: 1,
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
        indicator.currentLimit = 5000;
      }
    },

    requestAllIndicators(symbolID, timeframe) {
      for (const indicator of this.all) {
        if (indicator.hasExpandedHistory) continue;

        const queryParams = {
          symbol_id: symbolID,
          timeframe: timeframe,
          limit: indicator.currentLimit || 5000,
        };

        const body = {
          parameters: this.extractParameterValues(indicator.parameters),
        };

        this.requestIndicator(indicator._id, indicator.indicatorId, queryParams, body);
      }
    },

    async fetchOlderForAll(symbolID, timeframe, batchSize = 5000) {
      for (const indicator of this.all) {
        if (!indicator.data.length) continue;
        indicator.hasExpandedHistory = true;

        const earliestTs = indicator.data[0].timestamp.replace(/Z$/, '');
        const queryParams = { symbol_id: symbolID, timeframe, end_date: earliestTs, limit: batchSize };
        const body = { parameters: this.extractParameterValues(indicator.parameters) };

        await this.requestIndicatorPrepend(indicator._id, indicator.indicatorId, queryParams, body);
      }
    },

    async requestIndicator(_id, indicatorId, query, body = {}) {
      const params = new URLSearchParams(query).toString();

      try {
        const response = await fetch(`/api/indicator-api/indicators/${indicatorId}?${params}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(body),
        });

        const { data } = await response.json();

        this.handleMessageIndicatorInfo({
          _id,
          indicatorId,
          ...data,
        });
      } catch (error) {
        console.error("Error fetching indicator:", error);
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

    // mergePrepend(existing, incoming) {
    //   if (!Array.isArray(incoming) || incoming.length === 0) return existing;

    //   const existingSet = new Set(existing.map(d => d.timestamp));
    //   const uniqueOlder = incoming.filter(d => !existingSet.has(d.timestamp));

    //   if (!uniqueOlder.length) return existing;

    //   const merged = [...incoming, ...existing];
    //   merged.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    //   return merged;
    // },

    // Data processing
    handleMessageIndicatorInfo(indicatorResponse) {
      const {
        _id,
        indicatorId,
        indicator_info: indicatorInfo,
        indicator_data: indicatorData,
      } = indicatorResponse;
      const indicatorExists = _id !== null && this.indicators.has(_id);
      let newLocalId = _id;

      if (!indicatorExists) {
        newLocalId = this.addIndicator(
          indicatorInfo,
          indicatorData,
          indicatorId,
        );
      } else {
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
        data: [...data],
        parameters: finalParameters,
        styles: this.createStyles(info.outputs || {}),
        currentLimit: data.length || 5000,
        hasExpandedHistory: false,
      };
      this.indicators.set(_id, indicator);

      return _id;
    },

    updateIndicatorData(_id, newData) {
      const indicator = this.indicators.get(_id);

      if (!indicator) return;

      indicator.data = Array.isArray(newData) ? [...newData] : [];
      indicator.currentLimit = indicator.data.length;
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
