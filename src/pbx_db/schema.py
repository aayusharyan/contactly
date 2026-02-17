"""
PBX database ORM schema definitions.

Defines SQLAlchemy models for external MySQL database that PBX systems query for
caller-id name lookups. Single table design (PbxCnam) optimized for fast SELECT
queries during call processing. Keeps schema in sync between Python and SQL migrations.
"""

from sqlalchemy import Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class PbxCnam(Base):
    """
    Caller-id name lookup table for PBX systems.

    Stores phone number to display name mappings that Asterisk/FreePBX query during
    call processing. Minimal schema by design - only fields needed for caller-id lookup.
    Primary key on e164 enables fast lookups: "SELECT display_name FROM pbx_cnam WHERE
    e164 = '+14155551234'". Updated via sync_to_pbx() function after canonical merge.
    """

    __tablename__ = 'pbx_cnam'

    e164 = Column(String(20), primary_key=True, nullable=False, comment='Phone number in E.164 format')
    display_name = Column(String(500), nullable=False, comment='Contact display name for caller-id')
    updated_at = Column(DateTime, nullable=False, comment='Timestamp of last update')
    source = Column(String(50), nullable=True, comment='Winning source provider (google/icloud)')

    def __repr__(self):
        return f"<PbxCnam(e164={self.e164}, display_name={self.display_name})>"
