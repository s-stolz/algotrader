import { type DropdownProps, NPopover } from 'naive-ui';
import { designTokens } from '@/design/tokens';

const { color } = designTokens;

export const selectionColors = {
  surface: color.panel,
  hover: color.header,
  selected: color.selected,
  border: color.border,
  text: color.body,
  muted: color.muted,
  accent: color.interactive,
  controlBorder: color.controlBorder,
};

export const selectionPopoverTheme: NonNullable<
  InstanceType<typeof NPopover>['$props']['themeOverrides']
> = {
  color: selectionColors.surface,
  textColor: selectionColors.text,
  borderRadius: '6px',
  boxShadow: '0 8px 24px rgba(0, 0, 0, .4)',
  padding: '16px',
};

export const selectionDropdownTheme: NonNullable<
  DropdownProps['themeOverrides']
> = {
  color: selectionColors.surface,
  optionColorHover: selectionColors.hover,
  optionColorActive: selectionColors.selected,
  optionTextColor: selectionColors.text,
  optionTextColorHover: selectionColors.text,
  optionTextColorActive: selectionColors.text,
  dividerColor: selectionColors.border,
  borderRadius: '6px',
  padding: '4px',
  optionHeightMedium: '34px',
  peers: {
    Popover: {
      ...selectionPopoverTheme,
      boxShadow: `0 0 0 1px ${selectionColors.border}, 0 8px 24px rgba(0, 0, 0, .4)`,
    },
  },
};
