# ADR-0010: Bind market data to an immutable source

Status: Accepted

Date: 2026-11-15

## Context

A symbol name alone cannot distinguish broker data from an imported dataset.
Previously every stored Market could start a broker subscription, so a Custom
EURUSD dataset could receive the connected broker's EURUSD updates. Historical
backfill was also selected globally, although users need to choose older data
independently for each download.

## Decision

A Market has an immutable Broker or Custom source. Broker Markets bind to a
verified instrument, account, and environment at creation; Custom Markets receive
CSV data without broker activity. Live commands carry the local Market ID, and
all indicator dependencies must resolve to eligible Broker Markets. Existing
rows become Custom because their original source cannot be inferred reliably.

Historical extension is accepted one-time work owned by ingestion, persisted
through accessor transactions. It uses insert-only fenced pages, preserving
existing Candles. It is distinct from automatic live interruption recovery, which
retains authoritative broker upserts. Browser events invalidate snapshots; they
do not own job execution or store authoritative progress.

## Consequences

- Source changes require a new Market, preserving the meaning of stored Candles
  and Backtests instead of silently mixing datasets.
- Existing data survives the source migration, but existing rows stop receiving
  broker updates until users create verified Broker Markets.
- Downloads survive browser closure and service interruption without turning a
  user's one-time selection into a permanent history policy.
- Accessor schema, ingestion, live transport, indicators, and frontend must be
  deployed compatibly; older symbol-only consumers cannot enforce this boundary.

## References

- [Market sources and historical downloads](../contracts/market-data.md)
- [Pending recovery](../contracts/recovery.md)
- [Candle persistence](../contracts/candles.md)
