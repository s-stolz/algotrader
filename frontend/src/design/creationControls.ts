import type { CheckboxProps, DatePickerProps, DrawerProps } from 'naive-ui';
import { designTokens } from './tokens';

const { color, text, space, radius, shadow } = designTokens;
const border = (value: string) => `1px solid ${value}`;

export const designDrawerTheme: NonNullable<DrawerProps['themeOverrides']> = {
  color: color.inset,
  textColor: color.body,
  titleTextColor: color.body,
  titleFontSize: text.heading,
  bodyPadding: space.xl,
  headerPadding: space.xl,
  footerPadding: space.xl,
  headerBorderBottom: border(color.border),
  footerBorderTop: border(color.border),
  borderRadius: radius.panel,
  closeBorderRadius: radius.circle,
  closeSize: space.xl,
  closeIconColor: color.icon,
  closeIconColorHover: color.interactive,
  closeIconColorPressed: color.interactivePressed,
  closeColorHover: color.hover,
  closeColorPressed: color.selected,
  boxShadow: shadow.overlay,
};

export const designCheckboxTheme: NonNullable<CheckboxProps['themeOverrides']> =
  {
    color: color.inset,
    colorChecked: color.interactive,
    colorDisabled: color.disabled,
    colorDisabledChecked: color.disabled,
    checkMarkColor: color.onInteractive,
    border: border(color.controlBorder),
    borderChecked: border(color.interactive),
    borderFocus: border(color.interactive),
    borderDisabled: border(color.disabledBorder),
    borderDisabledChecked: border(color.disabledBorder),
    borderRadius: space.xs,
    textColor: color.body,
    textColorDisabled: color.disabledText,
    fontSizeSmall: text.secondary,
    fontSizeMedium: text.body,
    fontSizeLarge: text.body,
  };

export const designDatePickerTheme: NonNullable<
  DatePickerProps['themeOverrides']
> = {
  panelColor: color.panel,
  panelTextColor: color.body,
  panelBorderRadius: radius.panel,
  panelBoxShadow: shadow.overlay,
  itemTextColor: color.body,
  itemTextColorDisabled: color.disabledText,
  itemTextColorActive: color.onInteractive,
  itemTextColorCurrent: color.interactive,
  itemColorIncluded: color.selected,
  itemColorHover: color.hover,
  itemColorDisabled: color.disabled,
  itemColorActive: color.interactive,
  itemBorderRadius: radius.circle,
  scrollItemBorderRadius: radius.panel,
  itemFontSize: text.body,
  calendarDaysFontSize: text.secondary,
  calendarTitleFontSize: text.body,
  calendarTitleTextColor: color.body,
  calendarTitleColorHover: color.hover,
  calendarDaysTextColor: color.muted,
  arrowColor: color.icon,
  iconColor: color.icon,
  iconColorDisabled: color.disabledText,
  panelHeaderDividerColor: color.border,
  calendarDaysDividerColor: color.border,
  calendarDividerColor: color.border,
  panelActionDividerColor: color.border,
  panelExtraFooterPadding: space.md,
  panelActionPadding: space.md,
};
