import type { DataTableColumns } from 'naive-ui';
import type {
  StrategyCatalogEntry,
  BacktestPreviewCandidate,
} from '@/types/backtesterContracts';
import { TIMEFRAME_CODES } from '@/types/contracts';
const collator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: 'base',
});
function compareRows(
  a: BacktestPreviewCandidate,
  b: BacktestPreviewCandidate,
  select: (row: BacktestPreviewCandidate) => unknown,
): number {
  const left = select(a);
  const right = select(b);
  const compared =
    typeof left === 'number' && typeof right === 'number'
      ? left - right
      : collator.compare(String(left ?? ''), String(right ?? ''));
  return compared || a.candidate_ordinal - b.candidate_ordinal;
}
export function previewColumns(
  selectedStrategy: StrategyCatalogEntry | undefined,
): DataTableColumns<BacktestPreviewCandidate> {
  return [
    {
      title: '#',
      key: 'candidate_ordinal',
      width: 65,
      fixed: 'left',
      sorter: (a, b) => a.candidate_ordinal - b.candidate_ordinal,
      render: (row) => String(row.candidate_ordinal + 1),
    },
    {
      title: 'Market',
      key: 'market',
      sorter: (a, b) =>
        compareRows(
          a,
          b,
          (row) => `${row.market.symbol} ${row.market.exchange}`,
        ),
      render: (row) => `${row.market.symbol} · ${row.market.exchange}`,
    },
    {
      title: 'Timeframe',
      key: 'timeframe',
      sorter: (a, b) =>
        compareRows(a, b, (row) =>
          TIMEFRAME_CODES.indexOf(
            row.timeframe as (typeof TIMEFRAME_CODES)[number],
          ),
        ),
    },
    ...(selectedStrategy?.parameters ?? []).map((parameter) => ({
      title: parameter.display_name || parameter.name,
      key: `param-${parameter.name}`,
      sorter: (a: BacktestPreviewCandidate, b: BacktestPreviewCandidate) =>
        compareRows(a, b, (row) => row.parameters[parameter.name]),
      render: (row: BacktestPreviewCandidate) =>
        String(row.parameters[parameter.name]),
    })),
    {
      title: 'Allowed Directions',
      key: 'allowed_directions',
      sorter: (a, b) => compareRows(a, b, (row) => row.allowed_directions),
    },
    {
      title: 'State',
      key: 'status',
      sorter: (a, b) => compareRows(a, b, (row) => row.status),
      render: (row) =>
        row.status === 'ready'
          ? `Ready · Run #${(row.run_ordinal ?? 0) + 1}`
          : `Excluded · ${row.issues?.map((issue) => issue.message).join('; ') ?? ''}`,
    },
  ];
}
