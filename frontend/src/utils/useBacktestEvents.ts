import {
  onActivated,
  onDeactivated,
  onMounted,
  onUnmounted,
  ref,
  shallowRef,
} from 'vue';
import type {
  BacktestConnectionMessage,
  BacktestHealthMessage,
  BacktestProgressMessage,
} from '@/types/backtestEventContracts';
import { wsService } from './websocketService';

let subscribers = 0;

// Kept-alive consumers share one server subscription and detach while inactive.
export function useBacktestEvents(
  refresh: () => void,
  health?: (message: BacktestHealthMessage) => void,
) {
  const connected = ref(wsService.backtestsConnected);
  const progress = shallowRef(new Map(wsService.backtestProgress));
  let active = false;
  const changed = () => refresh();
  const connection = (message: BacktestConnectionMessage) => {
    connected.value = message.connected;
    if (message.connected) refresh();
  };
  const disconnected = () => {
    connected.value = false;
  };
  const heartbeat = (message: BacktestHealthMessage) => health?.(message);
  const advance = (message: BacktestProgressMessage) => {
    progress.value = new Map(wsService.backtestProgress).set(
      message.run_id,
      message,
    );
  };
  function start() {
    if (active) return;
    active = true;
    progress.value = new Map(wsService.backtestProgress);
    connected.value = wsService.backtestsConnected;
    wsService.on('backtestChanged', changed);
    wsService.on('backtestConnection', connection);
    wsService.on('backtestHealth', heartbeat);
    wsService.on('backtestProgress', advance);
    wsService.on('disconnected', disconnected);
    if (subscribers++ === 0) void wsService.send('subscribeBacktests');
  }
  function stop() {
    if (!active) return;
    active = false;
    wsService.off('backtestChanged', changed);
    wsService.off('backtestConnection', connection);
    wsService.off('backtestHealth', heartbeat);
    wsService.off('backtestProgress', advance);
    wsService.off('disconnected', disconnected);
    if (--subscribers === 0) void wsService.send('unsubscribeBacktests');
  }
  onMounted(start);
  onActivated(start);
  onDeactivated(stop);
  onUnmounted(stop);
  return { connected, progress };
}
