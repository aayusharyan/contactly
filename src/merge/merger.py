"""
Contactly - Contact Merging and Collision Resolution

Combines contacts from multiple sources (Google, iCloud) into canonical records using
latest-wins conflict resolution. When the same person exists in both Google and iCloud,
picks the most recently updated version as the winner. Groups contacts by phone number
identity (E.164 format) since phone numbers are the primary lookup key for PBX systems.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..internal_db.schema import CanonicalContact, SourceContact
from ..normalize import ContactNormalizer

logger = logging.getLogger(__name__)


class ContactMerger:
    """
    Merges contacts from multiple sources into canonical representation.

    Implements latest-wins collision resolution: when same phone number appears in
    multiple sources, picks the one with the most recent update timestamp. Falls back
    to source priority (Google > iCloud) as tiebreaker if timestamps are equal.
    """

    # Priority order for tiebreaking when timestamps are equal
    SOURCE_PRIORITY = ['google', 'icloud']

    def __init__(self, session: Session, normalizer: ContactNormalizer):
        """
        Initialize contact merger.

        Args:
            session: Database session
            normalizer: Contact normalizer for data standardization
        """
        self.session = session
        self.normalizer = normalizer

    def merge_all(self) -> Dict[str, Any]:
        """
        Merge all source contacts into canonical contacts.

        Groups source contacts by phone number (after E.164 normalization), then for
        each phone number selects the "winner" based on timestamps. Updates or creates
        canonical contacts with winning data. Removes stale canonical contacts for
        phone numbers that no longer exist in any source.

        Returns:
            Dictionary with merge statistics
        """
        stats = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0
        }

        logger.info("Starting contact merge process")

        source_contacts = self.session.query(SourceContact).all()

        # Group source contacts by normalized phone number
        phone_to_sources = {}
        for source in source_contacts:
            try:
                normalized = self.normalizer.normalize_contact(source.payload)
                phones = normalized.get('phones', [])

                # Each source contact can contribute multiple phone numbers
                for phone in phones:
                    if phone not in phone_to_sources:
                        phone_to_sources[phone] = []
                    phone_to_sources[phone].append((source, normalized))

            except Exception as e:
                logger.error(f"Failed to normalize source contact {source.id}: {e}")
                stats['skipped'] += 1

        # Merge each phone number identity
        for phone, sources_list in phone_to_sources.items():
            try:
                self._merge_phone_identity(phone, sources_list)
                stats['processed'] += 1
            except Exception as e:
                logger.error(f"Failed to merge phone identity {phone}: {e}")
                stats['skipped'] += 1

        # Clean up orphaned canonical contacts (phone numbers no longer in any source)
        existing_canonical = self.session.query(CanonicalContact).all()
        for canonical in existing_canonical:
            if canonical.best_e164 not in phone_to_sources:
                logger.info(f"Removing stale canonical contact {canonical.canonical_id}")
                self.session.delete(canonical)

        self.session.commit()

        stats['created'] = self.session.query(CanonicalContact).filter(
            CanonicalContact.created_at >= datetime.utcnow().replace(microsecond=0)
        ).count()
        stats['updated'] = stats['processed'] - stats['created']

        logger.info(f"Merge completed: {stats}")
        return stats

    def _merge_phone_identity(self, phone: str, sources_list: List[tuple[SourceContact, Dict[str, Any]]]):
        """
        Merge all sources for a single phone number identity.

        When multiple sources provide data for the same phone, picks the winner based
        on most recent source_updated_at timestamp. Updates canonical contact with
        winner's data and links all source contacts to this canonical record.

        Args:
            phone: E.164 phone number
            sources_list: List of (SourceContact, normalized_payload) tuples
        """
        winner = self._select_winner(sources_list)
        if not winner:
            logger.warning(f"No winner selected for phone {phone}")
            return

        source_contact, normalized = winner

        canonical = self.session.query(CanonicalContact).filter(
            CanonicalContact.best_e164 == phone
        ).first()

        display_name = normalized.get('display_name', 'Unknown')
        canonical_updated_at = source_contact.source_updated_at or source_contact.updated_at

        if canonical:
            # Update existing canonical only if new data is newer
            if canonical.canonical_updated_at < canonical_updated_at:
                canonical.best_display_name = display_name
                canonical.canonical_updated_at = canonical_updated_at
                canonical.extra_data = {
                    'winning_source': source_contact.source,
                    'given_name': normalized.get('given_name'),
                    'family_name': normalized.get('family_name'),
                    'emails': normalized.get('emails', [])
                }
                logger.debug(f"Updated canonical contact for {phone}")
        else:
            # Create new canonical contact
            canonical_id = self._generate_canonical_id(phone, source_contact)
            canonical = CanonicalContact(
                canonical_id=canonical_id,
                best_e164=phone,
                best_display_name=display_name,
                canonical_updated_at=canonical_updated_at,
                extra_data={
                    'winning_source': source_contact.source,
                    'given_name': normalized.get('given_name'),
                    'family_name': normalized.get('family_name'),
                    'emails': normalized.get('emails', [])
                }
            )
            self.session.add(canonical)
            logger.debug(f"Created canonical contact for {phone}")

        # Link all source contacts to the canonical record
        for src, _ in sources_list:
            if src.canonical_id != canonical.canonical_id:
                src.canonical_id = canonical.canonical_id

    def _select_winner(self, sources_list: List[tuple[SourceContact, Dict[str, Any]]]) -> Optional[tuple[SourceContact, Dict[str, Any]]]:
        """
        Select the winning source based on latest timestamp.

        Sorts by timestamp descending (most recent first), then by source priority
        (Google before iCloud) as tiebreaker. This ensures consistent behavior when
        contacts are updated simultaneously in multiple sources.

        Args:
            sources_list: List of source contacts with normalized data

        Returns:
            Winning (SourceContact, normalized_data) tuple or None
        """
        if not sources_list:
            return None

        # Helper to extract timestamp, falling back to datetime.min if missing
        def get_timestamp(item):
            source, _ = item
            return source.source_updated_at or source.updated_at or datetime.min

        # Helper to convert source name to priority index (lower is higher priority)
        def get_priority(item):
            source, _ = item
            try:
                return self.SOURCE_PRIORITY.index(source.source)
            except ValueError:
                return 999

        # Sort by timestamp DESC (most recent first), then by priority ASC (lower number = higher priority)
        sources_list.sort(key=lambda x: (get_timestamp(x), -get_priority(x)), reverse=True)

        return sources_list[0]

    def _generate_canonical_id(self, phone: str, source: SourceContact) -> str:
        """
        Generate a unique canonical ID for a new contact.

        Creates deterministic ID from phone suffix, source, and internal ID to enable
        debugging and manual database inspection. Format: canonical_{source}_{phone_suffix}_{id}

        Args:
            phone: E.164 phone number
            source: Primary source contact

        Returns:
            Canonical ID string
        """
        # Extract last 10 digits of phone for human-readable ID component
        phone_suffix = phone.replace('+', '').replace('-', '')[-10:]
        return f"canonical_{source.source}_{phone_suffix}_{source.id}"
