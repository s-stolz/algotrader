import type { SelectProps } from 'naive-ui';

export const baseSelectTheme: NonNullable<SelectProps['themeOverrides']> = {
  menuBoxShadow: '0 12px 32px rgba(0, 0, 0, .42)',
  peers: {
    InternalSelection: {
      color: '#171e27',
      colorActive: '#1b2630',
      colorDisabled: '#202833',
      textColor: '#dce4ed',
      textColorDisabled: '#8190a0',
      placeholderColor: '#8f9dab',
      placeholderColorDisabled: '#697988',
      arrowColor: '#9aafbf',
      arrowColorDisabled: '#697988',
      border: '1px solid #35414d',
      borderHover: '1px solid #63d2b0',
      borderActive: '1px solid #63d2b0',
      borderFocus: '1px solid #63d2b0',
      boxShadowHover: 'none',
      boxShadowActive: '0 0 0 2px rgba(99, 210, 176, .16)',
      boxShadowFocus: '0 0 0 2px rgba(99, 210, 176, .16)',
      borderRadius: '8px',
      caretColor: '#63d2b0',
    },
    InternalSelectMenu: {
      color: '#171e27',
      optionTextColor: '#dce4ed',
      optionTextColorPressed: '#dce4ed',
      optionTextColorDisabled: '#8190a0',
      optionTextColorActive: '#63d2b0',
      optionCheckColor: '#63d2b0',
      optionColorPending: '#253340',
      optionColorActive: '#1c3536',
      optionColorActivePending: '#254745',
      borderRadius: '6px',
    },
  },
};
