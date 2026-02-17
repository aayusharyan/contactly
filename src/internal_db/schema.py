"""
Local database schema definitions for contact storage.

Defines the internal SQLite database schema that stores contacts from all sources,
merge decisions, and sync state. This is NOT the external MySQL schema that PBX
systems query - that's managed by db_writer module. Three main tables: CanonicalContact
(merged view), SourceContact (per-provider raw data), and SyncState (token tracking).
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, Text, Index, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class CanonicalContact(Base):
    """
    Unified representation of a contact across all sources.

    Stores the "winning" contact data after merge resolution. Each canonical contact
    represents a unique phone number identity with the best available name. Multiple
    source contacts (from Google, iCloud) can point to the same canonical contact.
    """
    __tablename__ = 'canonical_contact'

    canonical_id = Column(String(255), primary_key=True)
    best_e164 = Column(String(20), index=True, nullable=False)
    best_display_name = Column(String(500), nullable=False)
    canonical_updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    source_contacts = relationship('SourceContact', back_populates='canonical')

    __table_args__ = (
        Index('idx_e164_updated', 'best_e164', 'canonical_updated_at'),
    )


class SourceContact(Base):
    """
    Per-source contact metadata for incremental sync tracking.

    Stores original contact data from each provider (Google, iCloud) along with
    provider-specific sync metadata (ETags, timestamps). Multiple source contacts
    can reference the same canonical contact through canonical_id foreign key.
    Enables tracking of which source provided the winning data.
    """
    __tablename__ = 'source_contact'

    id = Column(Integer, primary_key=True, autoincrement=True)

    canonical_id = Column(
        String(255),
        ForeignKey('canonical_contact.canonical_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    source = Column(String(50), nullable=False)
    source_contact_id = Column(String(500), nullable=False)

    payload = Column(JSON, nullable=False)

    source_updated_at = Column(DateTime, nullable=True)

    etag = Column(String(255), nullable=True)

    content_hash = Column(String(64), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    canonical = relationship('CanonicalContact', back_populates='source_contacts')

    __table_args__ = (
        Index('idx_source_contact', 'source', 'source_contact_id', unique=True),
        Index('idx_source_updated', 'source', 'source_updated_at'),
    )


class SyncState(Base):
    """
    Tracks synchronization state for each source.

    Stores sync cursors (Google) or ETags (iCloud), timestamps of last successful sync,
    and error information for debugging. One row per source (google, icloud). Sync
    cursors enable resumable synchronization - if sync fails midway, we can resume
    from last known good state rather than starting over.
    """
    __tablename__ = 'sync_state'

    source = Column(String(50), primary_key=True)

    sync_cursor = Column(Text, nullable=True)

    last_sync_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)

    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)

    sync_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
