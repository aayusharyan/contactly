"""
PBX database package for external database export.

Exports canonical contacts to external MySQL database that PBX systems (Asterisk,
FreePBX, etc.) query for caller-id name lookups. Maintains a simple pbx_cnam table
with (phone_number, display_name, timestamp) for fast caller-id resolution during
incoming/outgoing calls.

Uses ORM models (PbxCnam) as single source of truth for table structure.
Provides simple function-based API (no class wrappers).
"""

from .database import init_pbx_db, get_pbx_db_url, sync_to_pbx, verify_pbx_sync
from .schema import Base, PbxCnam

__all__ = ['init_pbx_db', 'get_pbx_db_url', 'sync_to_pbx', 'verify_pbx_sync', 'Base', 'PbxCnam']
