export function resolveWebsocketUrl(
  configured: string,
  pageUrl: string,
): string {
  const url = new URL(configured, pageUrl);
  if (url.protocol === 'http:') url.protocol = 'ws:';
  if (url.protocol === 'https:') url.protocol = 'wss:';
  if (url.protocol !== 'ws:' && url.protocol !== 'wss:') {
    throw new Error('WebSocket URL must use ws or wss');
  }
  return /^wss?:\/\//.test(configured) ? configured : url.toString();
}
