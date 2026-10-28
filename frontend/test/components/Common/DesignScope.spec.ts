import { mount } from '@vue/test-utils';
import { NAlert, NButton, NConfigProvider } from 'naive-ui';
import { h } from 'vue';
import { describe, expect, it, vi } from 'vitest';
import DesignScope from '@/components/Common/DesignScope.vue';
import { designTokens } from '@/design/tokens';

describe('DesignScope', () => {
  it('uses the shared error role for alert surfaces and icons', () => {
    const wrapper = mount(DesignScope, {
      slots: {
        default: () =>
          h(NAlert, { type: 'error' }, { default: () => 'Upload failed' }),
      },
    });
    const alert = wrapper.get('[role="alert"]').element as HTMLElement;
    expect(alert.style.getPropertyValue('--n-icon-color')).toBe(
      designTokens.color.error,
    );
    expect(alert.style.getPropertyValue('--n-color')).toBe(
      'rgba(233, 139, 139, 0.25)',
    );
    expect(alert.style.getPropertyValue('--n-border')).toBe(
      '1px solid rgba(233, 139, 139, 0.35)',
    );
    wrapper.unmount();
  });

  it('provides the selected visual roles without changing control events', async () => {
    const onClick = vi.fn();
    const wrapper = mount(DesignScope, {
      slots: {
        default: () => [
          h(NButton, { type: 'primary', onClick }, () => 'Apply'),
          h(NButton, { disabled: true, onClick }, () => 'Unavailable'),
          h(NButton, { circle: true, 'aria-label': 'Add' }, () => '+'),
        ],
      },
    });
    const theme = wrapper.getComponent(NConfigProvider).props('themeOverrides');
    expect(theme?.common).toMatchObject({
      fontFamily: 'Tektur, sans-serif',
      primaryColor: '#63e2b7',
      successColor: '#7dd5b4',
      textColor2: '#dce4ed',
      textColor3: '#8f9dab',
      fontSize: '13px',
    });
    expect(theme?.Button).toMatchObject({
      borderRadiusMedium: '999px',
      color: '#171e27',
      colorPrimary: '#63e2b7',
      colorDisabled: '#202833',
    });
    const scope = wrapper.get('.design-scope').element as HTMLElement;
    expect(scope.style.getPropertyValue('--design-text-heading')).toBe('17px');
    expect(scope.style.getPropertyValue('--design-text-metric')).toBe('27px');
    expect(scope.style.getPropertyValue('--design-text-secondary')).toBe(
      '12px',
    );
    expect(scope.style.getPropertyValue('--design-text-id')).toBe('11px');
    expect(scope.style.getPropertyValue('--design-space-xxl')).toBe('32px');
    expect(scope.style.getPropertyValue('--design-color-negative')).toBe(
      '#f0aaa2',
    );
    expect(wrapper.findAll('button')[1].attributes('disabled')).toBeDefined();
    await wrapper.findAll('button')[0].trigger('click');
    expect(onClick).toHaveBeenCalledOnce();
    await wrapper.findAll('button')[1].trigger('click');
    expect(onClick).toHaveBeenCalledOnce();
    wrapper.unmount();
  });
});
