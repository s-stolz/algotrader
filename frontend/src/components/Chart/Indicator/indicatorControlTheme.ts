import type { GlobalThemeOverrides } from 'naive-ui';
import { designTokens } from '@/design/tokens';

const { space } = designTokens;

export const indicatorControlTheme: GlobalThemeOverrides = {
  Tabs: {
    tabGapMediumLine: space.xl,
    tabPaddingMediumLine: `${space.sm} 0`,
    panePaddingMedium: `${space.md} 0 0 0`,
  },
};
