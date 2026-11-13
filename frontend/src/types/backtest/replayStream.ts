import { isRecord } from '../transportValues';
import {
  isEquityReplayResponse,
  type EquityReplayPoint,
  type EquityReplayResponse,
} from './results';

export type ReplayFrame =
  | { type: 'preview'; equity_curve: EquityReplayPoint[] }
  | { type: 'complete'; result: EquityReplayResponse }
  | { type: 'error'; message: string };

export function parseReplayFrame(line: string): ReplayFrame {
  const frame: unknown = JSON.parse(line);
  if (isRecord(frame)) {
    if (frame.type === 'error' && typeof frame.message === 'string')
      return { type: 'error', message: frame.message };
    if (frame.type === 'complete' && isEquityReplayResponse(frame.result))
      return { type: 'complete', result: frame.result };
    if (frame.type === 'preview' && Array.isArray(frame.equity_curve)) {
      const points = frame.equity_curve;
      if (
        points.length === 0 ||
        isEquityReplayResponse({
          availability: 'exact',
          reason: null,
          source_point_count: points.length,
          returned_point_count: points.length,
          sampled: false,
          equity_curve: points,
        })
      )
        return { type: 'preview', equity_curve: points };
    }
  }
  throw new Error('Invalid Equity Replay stream');
}
