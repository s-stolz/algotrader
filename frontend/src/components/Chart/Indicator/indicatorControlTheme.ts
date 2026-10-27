import type { GlobalThemeOverrides } from 'naive-ui';
import { designTokens } from '@/design/tokens';

const { color, space, text } = designTokens;

export const indicatorControlTheme: GlobalThemeOverrides = {
  Tabs: {
    tabFontSizeSmall: text.secondary,
    tabFontSizeMedium: text.body,
    tabFontSizeLarge: text.heading,
    tabGapMediumLine: space.xl,
    tabPaddingMediumLine: `${space.sm} 0`,
    tabTextColorLine: color.body,
    tabTextColorActiveLine: color.interactive,
    tabTextColorHoverLine: color.interactiveHover,
    tabTextColorDisabledLine: color.disabledText,
    barColor: color.interactive,
    panePaddingMedium: `${space.md} 0 0 0`,
  },
};
