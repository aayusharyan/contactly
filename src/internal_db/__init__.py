"""
Internal database package for local contact storage.

Provides SQLAlchemy ORM models and database session management for the canonical
contact database. This internal SQLite database serves as the sync state repository,
tracking contacts from multiple sources, merge conflicts, and sync tokens. Separate
from the external MySQL database that PBX systems query for caller-id lookups.
"""

from .schema import Base, CanonicalContact, SourceContact, SyncState
from .database import get_session, init_db

__all__ = [
    'Base',
    'CanonicalContact',
    'SourceContact',
    'SyncState',
    'get_session',
    'init_db',
]
