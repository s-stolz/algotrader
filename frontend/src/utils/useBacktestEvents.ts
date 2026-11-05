import { onActivated, onDeactivated, onMounted, onUnmounted, ref } from 'vue';
import type {
  BacktestConnectionMessage,
  BacktestHealthMessage,
} from '@/types/backtestEventContracts';
import { wsService } from './websocketService';

let subscribers = 0;

// Kept-alive consumers share one server subscription and detach while inactive.
export function useBacktestEvents(
  refresh: () => void,
  health?: (message: BacktestHealthMessage) => void,
) {
  const connected = ref(wsService.backtestsConnected);
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
  function start() {
    if (active) return;
    active = true;
    connected.value = wsService.backtestsConnected;
    wsService.on('backtestChanged', changed);
    wsService.on('backtestConnection', connection);
    wsService.on('backtestHealth', heartbeat);
    wsService.on('disconnected', disconnected);
    if (subscribers++ === 0) void wsService.send('subscribeBacktests');
  }
  function stop() {
    if (!active) return;
    active = false;
    wsService.off('backtestChanged', changed);
    wsService.off('backtestConnection', connection);
    wsService.off('backtestHealth', heartbeat);
    wsService.off('disconnected', disconnected);
    if (--subscribers === 0) void wsService.send('unsubscribeBacktests');
  }
  onMounted(start);
  onActivated(start);
  onDeactivated(stop);
  onUnmounted(stop);
  return { connected };
}
