-- Database indexes for query optimization
-- Creates indexes on frequently queried columns to improve lookup performance.
-- Includes composite indexes for common query patterns and unique constraints for data integrity.
-- All indexes use IF NOT EXISTS for idempotency.

-- Enables fast phone number lookups for incoming call identification
CREATE INDEX IF NOT EXISTS idx_canonical_e164 ON canonical_contact(best_e164);

-- Composite index for queries filtering by phone number and sorting by update time
CREATE INDEX IF NOT EXISTS idx_e164_updated ON canonical_contact(best_e164, canonical_updated_at);

-- Optimizes joins between source contacts and their canonical parent records
CREATE INDEX IF NOT EXISTS idx_source_canonical_id ON source_contact(canonical_id);

-- Enforces uniqueness and speeds up lookups for specific source provider contact IDs
CREATE UNIQUE INDEX IF NOT EXISTS idx_source_contact ON source_contact(source, source_contact_id);

-- Enables efficient incremental sync queries filtering by source and update timestamp
CREATE INDEX IF NOT EXISTS idx_source_updated ON source_contact(source, source_updated_at);
