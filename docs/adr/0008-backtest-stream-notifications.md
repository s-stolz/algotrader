# ADR-0008: Backtest Stream Notifications and Recovery

Status: Accepted

Date: 2026-11-04

## Decision

PostgreSQL remains authoritative for Backtest Run and Batch state. Redis Streams
carry invalidations to workers and the realtime-service. Workers use blocking
reads instead of periodic queue/cancellation HTTP reads. The existing browser
WebSocket carries backtest invalidations and health alongside market data.

Publication follows durable storage. Failed publication is retried in the
publisher process. On publisher startup, a reconciliation notification wakes
workers to read current state and browsers to refresh snapshots. Worker Redis
reconnection also requests reconciliation, even when stream history was lost or
trimmed. This closes the ordinary crash-before-publication case without an outbox
or periodic database scan. It deliberately depends on failed publishers being
restarted and failed connections recovering; delivery is not atomic with storage.

Messages are hints to read state, never permission to execute or cancel a process
without checking its durable identity. Each worker instance has a distinct,
restart-stable consumer group, and recovers its pending messages before reading
new ones. Acknowledgment follows successful handling; cancellation notifications
remain pending through confirmed exit and terminal settlement. Duplicate delivery
is harmless. ADR-0007 still requires operator recovery for a held execution slot.

## Consequences

- Redis Streams reuse existing infrastructure. Kafka and an outbox were rejected
  for this scope in favor of explicit publisher and consumer recovery.
- Publication retries and startup/reconnection reconciliation are required, not
  optional optimizations. A silently broken publisher that neither retries nor
  restarts is outside this recovery guarantee.
- Heartbeats retain health-only semantics. Persisted health evidence is forwarded
  to browsers; it never releases the slot or triggers cancellation/queue scans.
- realtime-service owns delivery to browsers; backtester retains lifecycle policy.
  Browser reconnection restores subscriptions and fetches authoritative snapshots.
  The gateway reports Redis outages even while the browser socket remains open.
- Stream retention is bounded. Recovery reads durable state rather than assuming
  that the stream is a complete lifecycle audit. Saved batch events remain the
  authoritative batch audit.

## References

- [Backtest contracts](../contracts/backtests.md#real-time-delivery-and-recovery)
- [Worker recovery](../operations/backtest-worker-recovery.md)
- [Realtime service](../../realtime-service/CONTEXT.md)
