import { h } from 'vue';
import { NButton, NIcon, NTooltip } from 'naive-ui';
import CopyOutline from '@vicons/ionicons5/es/CopyOutline';
import DocumentTextOutline from '@vicons/ionicons5/es/DocumentTextOutline';
import BarChartOutline from '@vicons/ionicons5/es/BarChartOutline';
import StopCircleOutline from '@vicons/ionicons5/es/StopCircleOutline';
import type { BacktestRun } from '@/types/backtesterContracts';
import { runName as comparisonRunLabel } from '../../backtestWorkspaceRuns';
import {
  executionLogAvailable,
  executionLogUnavailableReason,
} from '../workspaceExecution';
import type { BacktestWorkspace } from '../useBacktestWorkspace';
export function createComparisonRunActions(workspace: BacktestWorkspace) {
  const {
    openExecutionLog,
    openingChartRunId,
    overlayStore,
    chartUnavailableReason,
    openOnChart,
  } = workspace;
  const { cancellingRunIds, cancelRun } = workspace.commands;
  function executionLogAction(run: BacktestRun, label: string) {
    const available = executionLogAvailable(run);
    return h(NTooltip, null, {
      trigger: () =>
        h('span', { class: 'run-log-action' }, [
          h(
            NButton,
            {
              quaternary: true,
              circle: true,
              size: 'small',
              'data-testid': `workspace-log-${run.run_id}`,
              'aria-label': available
                ? `View execution log for ${label}`
                : `Execution log unavailable for ${label}`,
              disabled: !available,
              onKeydown: (event: KeyboardEvent) => {
                event.stopPropagation();
              },
              onClick: (event: MouseEvent) => {
                event.stopPropagation();
                if (!available) return;
                openExecutionLog(run);
              },
            },
            {
              icon: () =>
                h(
                  NIcon,
                  {
                    size: 16,
                    class: available ? undefined : 'unavailable-log-icon',
                  },
                  { default: () => h(DocumentTextOutline) },
                ),
            },
          ),
        ]),
      default: () =>
        available ? 'View execution log' : executionLogUnavailableReason(run),
    });
  }

  function analysisRunActions(run: BacktestRun) {
    return h('div', { class: 'row-actions' }, [
      h(
        NButton,
        {
          quaternary: true,
          circle: true,
          size: 'small',
          title: 'Create from this',
          'aria-label': `Create from ${comparisonRunLabel(run)}`,
          'data-testid': `workspace-create-from-run-${run.run_id}`,
          onKeydown: (event: KeyboardEvent) => event.stopPropagation(),
          onClick: (event: MouseEvent) => {
            event.stopPropagation();
            workspace.createFromRun(run);
          },
        },
        { icon: () => h(NIcon, { size: 16, component: CopyOutline }) },
      ),
      executionLogAction(run, comparisonRunLabel(run)),
      h(NTooltip, null, {
        trigger: () =>
          h('span', { class: 'run-chart-action' }, [
            h(
              NButton,
              {
                quaternary: true,
                circle: true,
                size: 'small',
                'data-testid': `workspace-chart-${run.run_id}`,
                'aria-label': `Open ${comparisonRunLabel(run)} on chart`,
                disabled:
                  openingChartRunId.value !== null ||
                  overlayStore.isLoading ||
                  !!chartUnavailableReason(run),
                loading: openingChartRunId.value === run.run_id,
                onKeydown: (event: KeyboardEvent) => {
                  event.stopPropagation();
                },
                onClick: (event: MouseEvent) => {
                  event.stopPropagation();
                  void openOnChart(run);
                },
              },
              {
                icon: () => h(NIcon, { size: 16, component: BarChartOutline }),
              },
            ),
          ]),
        default: () => chartUnavailableReason(run) ?? 'Open on chart',
      }),
      ...(['queued', 'running'].includes(run.status)
        ? [
            h(NTooltip, null, {
              trigger: () =>
                h(
                  NButton,
                  {
                    quaternary: true,
                    circle: true,
                    size: 'small',
                    'data-testid': `workspace-cancel-${run.run_id}`,
                    'aria-label': `Cancel ${comparisonRunLabel(run)}`,
                    disabled: cancellingRunIds.value.has(run.run_id),
                    loading: cancellingRunIds.value.has(run.run_id),
                    onKeydown: (event: KeyboardEvent) => {
                      event.stopPropagation();
                    },
                    onClick: (event: MouseEvent) => {
                      event.stopPropagation();
                      void cancelRun(run);
                    },
                  },
                  {
                    icon: () =>
                      h(NIcon, { size: 16, component: StopCircleOutline }),
                  },
                ),
              default: () => 'Cancel run',
            }),
          ]
        : []),
    ]);
  }

  return analysisRunActions;
}
