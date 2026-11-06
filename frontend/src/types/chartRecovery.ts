export interface ChartRecoveryQuery {
  symbol: string;
  timeframe: string;
  exchange: string | null;
  startMs: number;
  endMs: number;
}
