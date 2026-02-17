-- PBX caller-id name lookup table initialization
-- Creates simplified pbx_cnam table for fast phone number to display name lookups.
-- PBX systems (Asterisk, FreePBX) query this table during call processing using
-- "SELECT display_name FROM pbx_cnam WHERE e164 = '+14155551234'" pattern.
-- Single-table design with minimal columns keeps query performance optimal.
-- Uses IF NOT EXISTS for idempotent execution.

-- Stores phone number to display name mappings for caller-id lookups
-- Primary key on e164 enables fast lookups during active call processing
CREATE TABLE IF NOT EXISTS pbx_cnam (
    e164 VARCHAR(20) PRIMARY KEY NOT NULL,
    display_name VARCHAR(500) NOT NULL,
    updated_at DATETIME NOT NULL,
    source VARCHAR(50)
);
