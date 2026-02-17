-- Initial database schema setup migration
-- Creates foundational tables for contact aggregation from multiple sources (Google, iCloud).
-- This migration establishes three core tables: sync_state for tracking synchronization progress,
-- canonical_contact for merged/unified contact records, and source_contact for raw provider data.
-- All tables use idempotent CREATE IF NOT EXISTS to allow safe re-execution.

-- Tracks synchronization state and progress for each contact provider
-- Stores sync cursors/tokens to enable resumable incremental syncs and error tracking
CREATE TABLE IF NOT EXISTS sync_state (
    source VARCHAR(50) PRIMARY KEY COMMENT 'Provider identifier (google/icloud)',
    sync_cursor TEXT COMMENT 'Pagination token for resumable sync',
    last_sync_at DATETIME COMMENT 'Most recent sync attempt timestamp',
    last_success_at DATETIME COMMENT 'Last successful sync completion timestamp',
    last_error TEXT COMMENT 'Error message from most recent failure',
    error_count INTEGER NOT NULL DEFAULT 0 COMMENT 'Consecutive error count for backoff logic',
    sync_metadata JSON COMMENT 'Provider-specific sync metadata',
    created_at DATETIME NOT NULL COMMENT 'Record creation timestamp',
    updated_at DATETIME NOT NULL COMMENT 'Record last modification timestamp'
);

-- Stores unified contact records after merge resolution across all sources
-- Represents the "winning" contact data with best available phone number and display name
-- Acts as the single source of truth that gets written to external PBX/MySQL systems
CREATE TABLE IF NOT EXISTS canonical_contact (
    canonical_id VARCHAR(255) PRIMARY KEY COMMENT 'Unique identifier for unified contact',
    best_e164 VARCHAR(20) NOT NULL COMMENT 'Winning phone number in E.164 format',
    best_display_name VARCHAR(500) NOT NULL COMMENT 'Winning display name after merge resolution',
    canonical_updated_at DATETIME NOT NULL COMMENT 'Most recent update across all sources',
    extra_data JSON COMMENT 'Additional merged contact metadata',
    created_at DATETIME NOT NULL COMMENT 'Record creation timestamp'
);

-- Stores raw contact data from each provider for audit trail and conflict resolution
-- Multiple source contacts can reference the same canonical contact via foreign key
-- Preserves provider-specific metadata like ETags for efficient incremental syncing
CREATE TABLE IF NOT EXISTS source_contact (
    id INTEGER PRIMARY KEY AUTOINCREMENT COMMENT 'Auto-incrementing unique identifier',
    canonical_id VARCHAR(255) NOT NULL COMMENT 'Reference to parent canonical contact',
    source VARCHAR(50) NOT NULL COMMENT 'Provider identifier (google/icloud)',
    source_contact_id VARCHAR(500) NOT NULL COMMENT 'Provider-specific contact identifier',
    payload JSON NOT NULL COMMENT 'Raw contact data from provider API',
    source_updated_at DATETIME COMMENT 'Provider-reported last modification time',
    etag VARCHAR(255) COMMENT 'HTTP ETag for change detection',
    content_hash VARCHAR(64) COMMENT 'SHA-256 hash of payload for deduplication',
    created_at DATETIME NOT NULL COMMENT 'Record creation timestamp',
    updated_at DATETIME NOT NULL COMMENT 'Record last modification timestamp',
    FOREIGN KEY (canonical_id) REFERENCES canonical_contact(canonical_id) ON DELETE CASCADE
);
