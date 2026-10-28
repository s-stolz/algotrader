import {
  ColorType,
  CrosshairMode,
  type ChartOptions,
  type DeepPartial,
} from 'lightweight-charts';

import { designTokens } from '@/design/tokens';

const { color, font, text } = designTokens;

export function createDefaultChartOptions(
  options: DeepPartial<ChartOptions>,
): DeepPartial<ChartOptions> {
  return {
    grid: {
      vertLines: { color: 'transparent' },
      horzLines: { color: 'transparent' },
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: { color: color.muted, labelBackgroundColor: color.inset },
      horzLine: { color: color.muted, labelBackgroundColor: color.inset },
    },
    autoSize: true,
    ...options,
    layout: {
      textColor: color.body,
      fontFamily: font.ui,
      fontSize: Number.parseInt(text.secondary),
      background: { type: ColorType.Solid, color: 'transparent' },
      ...options.layout,
      panes: {
        separatorColor: color.border,
        ...options.layout?.panes,
      },
    },
  };
}
