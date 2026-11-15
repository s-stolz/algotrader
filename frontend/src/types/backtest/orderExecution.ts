export function isOrderExecution(value: Record<string, unknown>): boolean {
  const mode = value.execution_mode;
  const quote = value.candle_quote;
  const policy = value.intrabar_execution_policy;
  const spread = value.spread;
  const maximum = value.max_position_quantity;
  return (
    (mode === undefined || mode === 'targets' || mode === 'orders') &&
    (quote == null ||
      (typeof quote === 'string' && ['bid', 'ask', 'mid'].includes(quote))) &&
    (mode !== 'orders' || quote != null) &&
    (policy == null ||
      (typeof policy === 'string' &&
        ['conservative', 'optimistic', 'error'].includes(policy))) &&
    (spread === undefined ||
      (typeof spread === 'number' && Number.isFinite(spread) && spread >= 0)) &&
    (maximum == null ||
      (typeof maximum === 'number' &&
        Number.isFinite(maximum) &&
        maximum > 0)) &&
    (mode === 'orders' || ((!spread || spread === 0) && maximum == null))
  );
}
