import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import BaseAsyncState from '@/components/Common/BaseAsyncState.vue';

describe('async state feedback', () => {
  it('names loading for assistive technology and marks its region busy', () => {
    const wrapper = mount(BaseAsyncState, {
      props: { kind: 'loading', label: 'Loading runs' },
    });
    expect(wrapper.get('[role="status"]').attributes()).toMatchObject({
      'aria-label': 'Loading runs',
      'aria-busy': 'true',
    });
    wrapper.unmount();
  });
  it('offers a named retry control for an error and blocks it while retrying', async () => {
    const wrapper = mount(BaseAsyncState, {
      props: {
        kind: 'error',
        label: 'Runs unavailable',
        message: 'Couldn’t load runs',
        retry: true,
      },
    });
    expect(wrapper.get('[role="alert"]').text()).toContain(
      'Couldn’t load runs',
    );
    const retry = wrapper.get('button[aria-label="Retry: Runs unavailable"]');
    await retry.trigger('click');
    expect(wrapper.emitted('retry')).toHaveLength(1);
    await wrapper.setProps({ retrying: true });
    expect(retry.attributes('disabled')).toBeDefined();
    wrapper.unmount();
  });
});
