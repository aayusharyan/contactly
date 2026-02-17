-- PBX database indexes for query optimization
-- Adds indexes to pbx_cnam table for improved lookup performance during call processing.
-- All indexes use IF NOT EXISTS for idempotency.

-- Optimizes queries filtering by phone number and sorting by update timestamp
-- Useful for finding recently updated caller-id entries
CREATE INDEX IF NOT EXISTS idx_pbx_e164_updated ON pbx_cnam(e164, updated_at);

-- Enables efficient lookups by source provider for debugging and auditing
-- Helps identify which contact source provided the winning display name
CREATE INDEX IF NOT EXISTS idx_pbx_source ON pbx_cnam(source);
