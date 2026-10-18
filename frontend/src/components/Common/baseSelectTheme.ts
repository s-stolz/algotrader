import type { SelectProps } from 'naive-ui';
import { selectionColors } from './selectionTheme';

export const baseSelectTheme: NonNullable<SelectProps['themeOverrides']> = {
  menuBoxShadow: `0 0 0 1px ${selectionColors.border}, 0 12px 32px rgba(0, 0, 0, .42)`,
  peers: {
    InternalSelection: {
      color: selectionColors.surface,
      colorActive: selectionColors.surface,
      colorDisabled: '#202833',
      textColor: '#dce4ed',
      textColorDisabled: '#8190a0',
      placeholderColor: '#8f9dab',
      placeholderColorDisabled: '#697988',
      arrowColor: '#9aafbf',
      arrowColorDisabled: '#697988',
      border: `1px solid ${selectionColors.controlBorder}`,
      borderHover: `1px solid ${selectionColors.accent}`,
      borderActive: `1px solid ${selectionColors.accent}`,
      borderFocus: `1px solid ${selectionColors.accent}`,
      boxShadowHover: 'none',
      boxShadowActive: 'none',
      boxShadowFocus: 'none',
      borderRadius: '34px',
      caretColor: selectionColors.accent,
    },
    InternalSelectMenu: {
      color: selectionColors.surface,
      optionTextColor: '#dce4ed',
      optionTextColorPressed: '#dce4ed',
      optionTextColorDisabled: '#8190a0',
      optionTextColorActive: selectionColors.text,
      optionCheckColor: selectionColors.accent,
      optionColorPending: selectionColors.hover,
      optionColorActive: selectionColors.selected,
      optionColorActivePending: selectionColors.selected,
      borderRadius: '6px',
    },
  },
};
