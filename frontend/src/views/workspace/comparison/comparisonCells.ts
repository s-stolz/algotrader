import { h } from 'vue';
import { NIcon, NTooltip } from 'naive-ui';
import {
  TimeOutline,
  PlayCircleOutline,
  HourglassOutline,
  CheckmarkCircleOutline,
  CloseCircleOutline,
  BanOutline,
} from '@vicons/ionicons5';
import type {
  BacktestRun,
  BacktestRunStatus,
} from '@/types/backtesterContracts';
import {
  savedMetric,
  formatMagnitude,
  formatSigned,
} from '../../backtestWorkspaceRuns';
export function cell(value: string, explanation?: string) {
  return h(
    'span',
    {
      title: explanation ?? value,
      class: 'ellipsis-cell',
      style: {
        display: 'block',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      },
    },
    value,
  );
}

export function metricCell(
  run: BacktestRun,
  key: string,
  explanation: string,
  suffix = '',
  positiveMagnitude = false,
) {
  const value = run.status === 'succeeded' ? savedMetric(run, key) : null;
  const display = positiveMagnitude
    ? formatMagnitude(value, suffix)
    : formatSigned(value, suffix);
  return h(
    'span',
    {
      class:
        value == null || positiveMagnitude
          ? undefined
          : value < 0
            ? 'negative-metric'
            : value > 0
              ? 'positive-metric'
              : undefined,
    },
    cell(display, explanation),
  );
}
export function countCell(run: BacktestRun, key: string, explanation: string) {
  return cell(
    run.status === 'succeeded'
      ? (savedMetric(run, key)?.toString() ?? '—')
      : '—',
    explanation,
  );
}
export function directionPnl(run: BacktestRun, direction: 'long' | 'short') {
  if (run.status !== 'succeeded') return cell('—');
  const count = savedMetric(run, `${direction}_trade_count`);
  const pnl = count === 0 ? 0 : savedMetric(run, `${direction}_realized_pnl`);
  return cell(
    formatSigned(pnl),
    'Saved sum of realized PnL from ' +
      direction +
      ' Closed Trades, signed account units. Zero when there were no trades.',
  );
}
const runStatusIcons = {
  queued: { icon: TimeOutline, label: 'Queued', color: '#9aafbf' },
  running: { icon: PlayCircleOutline, label: 'Running', color: '#70c0e8' },
  cancelling: { icon: HourglassOutline, label: 'Cancelling', color: '#e8bc70' },
  succeeded: {
    icon: CheckmarkCircleOutline,
    label: 'Succeeded',
    color: '#7cd8b7',
  },
  failed: { icon: CloseCircleOutline, label: 'Failed', color: '#e88b8b' },
  cancelled: { icon: BanOutline, label: 'Cancelled', color: '#9aafbf' },
} satisfies Record<
  BacktestRunStatus,
  { icon: typeof TimeOutline; label: string; color: string }
>;

export function runStatusCell(run: BacktestRun) {
  const { icon, label, color } = runStatusIcons[run.status];
  return h(NTooltip, null, {
    trigger: () =>
      h(
        'span',
        {
          class: 'run-status-icon',
          role: 'img',
          'aria-label': label,
          tabindex: 0,
        },
        h(NIcon, {
          component: icon,
          size: 20,
          color,
          'aria-hidden': true,
        }),
      ),
    default: () => label,
  });
}
