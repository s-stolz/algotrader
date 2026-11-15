import { computed, onMounted, onUnmounted, ref } from 'vue';
import {
  changeHistoryDownload,
  fetchHistoryDownloads,
  fetchMarketCoverage,
  requestHistoryDownload,
} from '@/api/historyDownloadClient';
import {
  isDownloadActive,
  type HistoryDownload,
  type HistoryDownloadRequest,
  type MarketCoverage,
  type HistoryDownloadChanged,
  type HistoryDownloadsConnection,
} from '@/types/historyDownloadContracts';
import { wsService } from '@/utils/websocketService';

export function useHistoryDownloads(marketId: number) {
  const coverage = ref<MarketCoverage | null>(null);
  const downloads = ref<HistoryDownload[]>([]);
  const loading = ref(true);
  const submitting = ref(false);
  const error = ref('');
  const connected = ref(false);
  const mode = ref<'date' | 'count'>('date');
  const startDate = ref('');
  const candleCount = ref<number | null>(10000);
  const current = computed(
    () => downloads.value.find(isDownloadActive) ?? downloads.value[0] ?? null,
  );
  const active = computed(
    () => current.value !== null && isDownloadActive(current.value),
  );
  let alive = true;
  let refreshing: Promise<void> | null = null;
  let dirty = false;
  let request: HistoryDownloadRequest | null = null;
  let requestSignature = '';

  function install(jobs: HistoryDownload[]) {
    const byId = new Map(downloads.value.map((job) => [job.id, job]));
    for (const job of jobs) {
      if ((byId.get(job.id)?.revision ?? -1) <= job.revision)
        byId.set(job.id, job);
    }
    downloads.value = [...byId.values()]
      .sort(
        (left, right) =>
          Number(isDownloadActive(right)) - Number(isDownloadActive(left)) ||
          right.created_at.localeCompare(left.created_at),
      )
      .slice(0, 100);
  }

  function refresh(): Promise<void> {
    dirty = true;
    if (refreshing) return refreshing;
    refreshing = (async () => {
      while (alive && dirty) {
        dirty = false;
        try {
          const [nextCoverage, jobs] = await Promise.all([
            fetchMarketCoverage(marketId),
            fetchHistoryDownloads(marketId),
          ]);
          if (!alive) return;
          coverage.value = nextCoverage;
          install(jobs);
          error.value = '';
        } catch (cause) {
          if (alive)
            error.value =
              cause instanceof Error
                ? cause.message
                : 'Unable to load download status';
        } finally {
          if (alive) loading.value = false;
        }
      }
    })().finally(() => {
      refreshing = null;
    });
    return refreshing;
  }

  async function submit() {
    if (submitting.value || active.value) return;
    error.value = '';
    if (mode.value === 'date') {
      const parsed = Date.parse(`${startDate.value}T00:00:00Z`);
      if (
        !/^\d{4}-\d{2}-\d{2}$/.test(startDate.value) ||
        !Number.isFinite(parsed) ||
        parsed < 0 ||
        new Date(parsed).toISOString().slice(0, 10) !== startDate.value ||
        parsed >=
          (coverage.value?.oldest_timestamp_ms ??
            Math.floor(Date.now() / 60000) * 60000)
      ) {
        error.value =
          'Choose a UTC date before the oldest stored candle, from 1970 onward.';
        return;
      }
    } else if (
      !Number.isInteger(candleCount.value) ||
      candleCount.value === null ||
      candleCount.value < 1 ||
      candleCount.value > 1000000
    ) {
      error.value = 'Enter between 1 and 1,000,000 one-minute candles.';
      return;
    }
    const signature = JSON.stringify([
      mode.value,
      startDate.value,
      candleCount.value,
    ]);
    if (!request || signature !== requestSignature) {
      requestSignature = signature;
      request = {
        request_id: crypto.randomUUID(),
        market_id: marketId,
        ...(mode.value === 'date'
          ? { start_date: startDate.value }
          : { candle_count: candleCount.value! }),
      };
    }
    await command(async () => {
      const accepted = await requestHistoryDownload(request!);
      request = null;
      return accepted;
    });
  }

  async function command(action: () => Promise<HistoryDownload>) {
    submitting.value = true;
    error.value = '';
    try {
      const job = await action();
      if (!alive) return;
      install([job]);
      await refresh();
    } catch (cause) {
      if (alive)
        error.value =
          cause instanceof Error ? cause.message : 'Unable to update download';
    } finally {
      if (alive) submitting.value = false;
    }
  }

  async function change(action: 'cancel' | 'retry') {
    if (!current.value || submitting.value) return;
    const id = current.value.id;
    await command(() => changeHistoryDownload(id, action));
  }

  function changed(message: HistoryDownloadChanged) {
    if (message.market_id === marketId) void refresh();
  }
  function connection(message: HistoryDownloadsConnection) {
    if (message.market_id !== marketId) return;
    connected.value = message.connected;
    if (message.connected) void refresh();
  }
  const ready = () => {
    void refresh();
  };
  const disconnected = () => {
    connected.value = false;
  };
  onMounted(() => {
    wsService.on('historyDownloadChanged', changed);
    wsService.on('historyDownloadsConnection', connection);
    wsService.on('ready', ready);
    wsService.on('disconnected', disconnected);
    void wsService.send('subscribeHistoryDownloads', { market_id: marketId });
    void refresh();
  });
  onUnmounted(() => {
    alive = false;
    wsService.off('historyDownloadChanged', changed);
    wsService.off('historyDownloadsConnection', connection);
    wsService.off('ready', ready);
    wsService.off('disconnected', disconnected);
    void wsService.send('unsubscribeHistoryDownloads', { market_id: marketId });
  });
  return {
    coverage,
    downloads,
    current,
    active,
    loading,
    submitting,
    error,
    connected,
    mode,
    startDate,
    candleCount,
    submit,
    change,
    refresh,
  };
}
