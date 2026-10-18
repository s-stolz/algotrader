# Historical Candle contract

Broker owns retrieval of broker-available Candles. Ingestion owns the history
interval and closed-M1 boundary. Times are UTC epoch milliseconds; request
`fromTs` and `toTs` are inclusive. Empty intervals, weekends, holidays and periods
without trades are valid. No timestamp density or synthetic Candle is required.

## Streaming completion

`GET /symbols/{symbol}/trendbars/stream` returns NDJSON. Candle records retain
`o`, `h`, `l`, `c`, `v`, `t`, and `digits`. Exactly one terminal record confirms
successful retrieval:

```json
{"type":"complete","version":1,"count":0,"fromTs":60000,"toTs":119999,"limit":null}
```

The terminal record echoes the requested bounds and limit and counts the Candle
records actually sent. `limit: null` means the complete requested interval;
a supplied limit intentionally caps delivery. On failure, including after some
Candles, the server sends `{"type":"error","message":"Historical download failed"}`
and never sends completion. Connection failure can prevent even that error record.

The actual ingestion consumer requires matching completion and count followed by
ordinary EOF. It rejects error records, missing completion, malformed records,
mismatched bounds/count, and records following completion. Partial delivery is
not successful backfill. A successful count of zero completes an empty interval.
Deploy broker and ingestion together: older producers omit completion, and older
consumers do not understand the terminal record. Restart ingestion after upgrade;
this contract alone does not provide durable recovery across restart.

## cTrader pagination

The [provider message contract](https://help.ctrader.com/open-api/messages/#protooagettrendbarsreq)
defines `count` as a limit backwards from `toTimestamp`. `hasMore` is optional in
the current provider schema and absent from the installed 0.9.2 Python SDK.
Neither a short response nor a requested window's end proves exhaustion.

Finite time windows bound streaming memory. Within each window the adapter asks
backwards, moves `toTimestamp` to one millisecond before the earliest returned
Candle, and continues even after a short page. An empty residual response or
reaching the inclusive lower bound completes that window. Nonadvancing results
and incomplete/unexpected protobuf responses fail explicitly.
Count-based responses can extend before `fromTimestamp`; those older bars are
excluded from output and establish that the lower bound has been reached.
Duplicate timestamps or bars newer than the page end still fail explicitly.
Empty windows do not stop retrieval of later windows. Unspecified end time is
frozen once. Limited nonstreaming queries retain the most recent Candle selection.

## Verification

The broker router suite drives the actual ingestion HTTP consumer through the
FastAPI route and cTrader adapter using controlled provider responses. It covers
capped short pages, empty windows, empty completion, failure before/after delivery,
incomplete EOF, count/bound verification, and limited-query compatibility.
The suite requires broker and ingestion dependencies, including `httpx`.
