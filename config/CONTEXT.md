# Configuration vocabulary

**History policy** selects a fresh ingestion recovery boundary from a rolling
lookback or a quoted UTC start date. Accepted pending recovery retains its earlier
boundary when this policy changes. For configuration and deployment obligations,
read the [recovery contract](../docs/contracts/recovery.md); field types and
runtime mappings are in [topology schema](topology.schema.md).
