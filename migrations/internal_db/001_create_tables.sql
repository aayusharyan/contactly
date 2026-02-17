-- Initial database schema setup migration
-- Creates foundational tables for contact aggregation from multiple sources (Google, iCloud).
-- This migration establishes three core tables: sync_state for tracking synchronization progress,
-- canonical_contact for merged/unified contact records, and source_contact for raw provider data.
-- All tables use idempotent CREATE IF NOT EXISTS to allow safe re-execution.

-- Tracks synchronization state and progress for each contact provider
-- Stores sync cursors/tokens to enable resumable incremental syncs and error tracking
CREATE TABLE IF NOT EXISTS sync_state (
    source VARCHAR(50) PRIMARY KEY,
    sync_cursor TEXT,
    last_sync_at DATETIME,
    last_success_at DATETIME,
    last_error TEXT,
    error_count INTEGER NOT NULL DEFAULT 0,
    sync_metadata JSON,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

-- Stores unified contact records after merge resolution across all sources
-- Represents the "winning" contact data with best available phone number and display name
-- Acts as the single source of truth that gets written to external PBX/MySQL systems
CREATE TABLE IF NOT EXISTS canonical_contact (
    canonical_id VARCHAR(255) PRIMARY KEY,
    best_e164 VARCHAR(20) NOT NULL,
    best_display_name VARCHAR(500) NOT NULL,
    canonical_updated_at DATETIME NOT NULL,
    extra_data JSON,
    created_at DATETIME NOT NULL
);

-- Stores raw contact data from each provider for audit trail and conflict resolution
-- Multiple source contacts can reference the same canonical contact via foreign key
-- Preserves provider-specific metadata like ETags for efficient incremental syncing
CREATE TABLE IF NOT EXISTS source_contact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_id VARCHAR(255) NOT NULL,
    source VARCHAR(50) NOT NULL,
    source_contact_id VARCHAR(500) NOT NULL,
    payload JSON NOT NULL,
    source_updated_at DATETIME,
    etag VARCHAR(255),
    content_hash VARCHAR(64),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (canonical_id) REFERENCES canonical_contact(canonical_id) ON DELETE CASCADE
);
