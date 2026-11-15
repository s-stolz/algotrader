import { expect, it } from 'vitest';
import { resolveWebsocketUrl } from '@/utils/websocketUrl';

it('resolves the packaged socket against the selected application port', () => {
  expect(resolveWebsocketUrl('/ws', 'http://localhost:8088/chart')).toBe(
    'ws://localhost:8088/ws',
  );
  expect(resolveWebsocketUrl('/ws', 'https://localhost:8443/chart')).toBe(
    'wss://localhost:8443/ws',
  );
});
it('preserves explicitly configured development endpoints', () => {
  expect(
    resolveWebsocketUrl('ws://localhost:8765', 'http://localhost:5173'),
  ).toBe('ws://localhost:8765');
  expect(() =>
    resolveWebsocketUrl('file:///tmp/socket', 'http://localhost'),
  ).toThrow('must use ws or wss');
});
