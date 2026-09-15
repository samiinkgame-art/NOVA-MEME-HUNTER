# 001: additive integrity schema
Stop the previous service and back up its database before migration. Run `python migrations/001_integrity.py` from backend root with the intended DATABASE_URL. Startup invokes the same create_all/recovery path. No columns are dropped.

Adds nova_intents, nova_exact_positions, nova_ledger, nova_observation_state and public launch event storage, plus KV state for sequence, reconciliation anchor, UTC periods, kill/cooldowns. Legacy positions are imported as LEGACY_FLOAT_IMPORT; prior precision cannot be recovered. Historical fills are not reconstructed.

Migration is idempotent. Recovery disables automatic entries until a deliberate restart from the dashboard. A reconciliation mismatch sets kill. Do not manually set recovery_ok to bypass a mismatch.

Rollback: stop this service; restore BOTH old source and its pre-upgrade database backup. Do not run the old writer against an integrity-upgraded account: the old writer does not maintain the new ledger. No destructive down migration is supplied.
