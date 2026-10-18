import { darkTheme, type DropdownProps, NPopover } from 'naive-ui';

export const selectionColors = {
  surface: '#131722',
  hover: '#222a38',
  selected: '#2a3445',
  border: '#2b3541',
  text: '#dce4ed',
  muted: '#8f9dab',
  accent: darkTheme.common?.primaryColor ?? '#63e2b7',
  controlBorder: darkTheme.common?.borderColor ?? 'rgba(255, 255, 255, .24)',
};

export const selectionPopoverTheme: NonNullable<InstanceType<typeof NPopover>['$props']['themeOverrides']> = {
  color: selectionColors.surface,
  textColor: selectionColors.text,
  borderRadius: '6px',
  boxShadow: '0 8px 24px rgba(0, 0, 0, .4)',
  padding: '16px',
};

export const selectionDropdownTheme: NonNullable<DropdownProps['themeOverrides']> = {
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
