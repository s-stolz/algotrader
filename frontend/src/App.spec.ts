import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import App from './App.vue';

const websocketMock = vi.hoisted(() => ({
  close: vi.fn(),
}));

vi.mock('./utils/websocketService', () => ({
  wsService: {
    close: websocketMock.close,
  },
}));

describe('App', () => {
  it('closes the explicit WebSocket service dependency when unmounted', () => {
    const wrapper = mount(App, {
      global: {
        stubs: {
          'n-config-provider': {
            template: '<div><slot /></div>',
          },
          'router-view': true,
        },
      },
    });

    wrapper.unmount();

    expect(websocketMock.close).toHaveBeenCalledOnce();
  });
});
