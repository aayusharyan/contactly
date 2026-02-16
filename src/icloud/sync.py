"""
iCloud contacts synchronization coordinator.

Orchestrates the complete sync workflow: fetch contact list with ETags, compare with
local database, download only changed contacts, parse vCards, and store normalized data.
Implements robust error handling and tracks sync state for resumable operations. Uses
ETag-based incremental sync to minimize bandwidth and API calls.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Set
from sqlalchemy.orm import Session
import vobject
from email.utils import parsedate_to_datetime

from .client import ICloudCardDAVClient
from ..storage.schema import SourceContact, SyncState

logger = logging.getLogger(__name__)


class ICloudContactsSync:
    """
    Manages synchronization of contacts from iCloud CardDAV.

    Coordinates ETag comparison, contact fetching, vCard parsing, and database updates.
    Maintains sync state to enable efficient incremental synchronization without
    re-downloading unchanged contacts.
    """

    SOURCE_NAME = 'icloud'

    def __init__(self, client: ICloudCardDAVClient, session: Session):
        """
        Initialize sync coordinator.

        Args:
            client: Authenticated iCloud CardDAV client
            session: Database session for storing contacts
        """
        self.client = client
        self.session = session

    def sync(self) -> Dict[str, Any]:
        """
        Perform contact synchronization from iCloud.

        Compares remote ETags with local database to identify new, updated, and deleted
        contacts. Only fetches contacts that have changed, making subsequent syncs very
        fast. Handles deletions by comparing remote href list with local records.

        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'added': 0,
            'updated': 0,
            'deleted': 0,
            'unchanged': 0,
            'errors': 0
        }

        try:
            logger.info("Starting iCloud sync")

            # Fetch contact list with metadata from server
            remote_contacts = self.client.list_contacts_with_etags()

            existing_contacts = self._get_existing_contacts()

            # Find contacts that were deleted on iCloud
            remote_hrefs = {c['href'] for c in remote_contacts}
            existing_hrefs = set(existing_contacts.keys())

            deleted_hrefs = existing_hrefs - remote_hrefs
            for href in deleted_hrefs:
                self._delete_contact(href)
                stats['deleted'] += 1

            # Build list of contacts to fetch (new or changed ETags)
            to_fetch = []
            for contact_info in remote_contacts:
                href = contact_info['href']
                etag = contact_info['etag']

                if href in existing_contacts:
                    existing_etag = existing_contacts[href].etag
                    # Skip if ETag matches (contact unchanged)
                    if existing_etag == etag:
                        stats['unchanged'] += 1
                        continue

                to_fetch.append(contact_info)

            logger.info(f"Fetching {len(to_fetch)} changed/new contacts")

            # Download vCard data for changed contacts
            vcards = self.client.fetch_multiple_vcards([c['href'] for c in to_fetch])

            # Process each fetched vCard
            for contact_info, (href, vcard) in zip(to_fetch, vcards):
                try:
                    if vcard is None:
                        logger.warning(f"Failed to fetch vCard for {href}")
                        stats['errors'] += 1
                        continue

                    is_new = href not in existing_contacts
                    self._process_vcard(href, vcard, contact_info, is_new)

                    if is_new:
                        stats['added'] += 1
                    else:
                        stats['updated'] += 1

                except Exception as e:
                    logger.error(f"Error processing vCard {href}: {e}")
                    stats['errors'] += 1

            self._update_sync_state(success=True)
            self.session.commit()

            logger.info(f"iCloud sync completed: {stats}")

        except Exception as e:
            logger.error(f"iCloud sync failed: {e}")
            self._update_sync_state(success=False, error=str(e))
            raise

        return stats

    def _get_existing_contacts(self) -> Dict[str, SourceContact]:
        """
        Retrieve all existing iCloud contacts from database.
        Maps href to contact object for efficient ETag comparison.

        Returns:
            Dictionary mapping href to SourceContact
        """
        contacts = self.session.query(SourceContact).filter(
            SourceContact.source == self.SOURCE_NAME
        ).all()

        return {c.source_contact_id: c for c in contacts}

    def _delete_contact(self, href: str):
        """
        Delete a contact that no longer exists in iCloud.
        Handles cascade deletion of related records through foreign key constraints.
        """
        contact = self.session.query(SourceContact).filter(
            SourceContact.source == self.SOURCE_NAME,
            SourceContact.source_contact_id == href
        ).first()

        if contact:
            self.session.delete(contact)
            logger.debug(f"Deleted contact {href}")

    def _process_vcard(self, href: str, vcard: vobject.vCard, contact_info: Dict[str, Any], is_new: bool):
        """
        Process a vCard and create/update database record.

        Extracts timestamp from multiple sources (HTTP Last-Modified header, vCard REV field)
        to track when contact was last changed. Normalizes vCard structure into JSON payload
        for easier querying and processing downstream.

        Args:
            href: Contact resource URL
            vcard: Parsed vCard object
            contact_info: Metadata including etag
            is_new: Whether this is a new contact
        """
        normalized = self._normalize_vcard(vcard)

        # Try to extract timestamp from Last-Modified header
        source_updated_at = None
        if contact_info.get('last_modified'):
            try:
                source_updated_at = parsedate_to_datetime(contact_info['last_modified'])
            except Exception:
                pass

        # Prefer REV field from vCard if available (more accurate)
        if hasattr(vcard, 'rev'):
            try:
                rev_value = vcard.rev.value
                if isinstance(rev_value, datetime):
                    source_updated_at = rev_value
                elif isinstance(rev_value, str):
                    source_updated_at = datetime.fromisoformat(rev_value.replace('Z', '+00:00'))
            except Exception:
                pass

        # Extract UID or generate from href
        uid = vcard.uid.value if hasattr(vcard, 'uid') else href.split('/')[-1].replace('.vcf', '')

        if is_new:
            new_contact = SourceContact(
                canonical_id=f"icloud_{uid}",
                source=self.SOURCE_NAME,
                source_contact_id=href,
                payload=normalized,
                source_updated_at=source_updated_at,
                etag=contact_info.get('etag')
            )
            self.session.add(new_contact)
            logger.debug(f"Added new contact {href}")
        else:
            contact = self.session.query(SourceContact).filter(
                SourceContact.source == self.SOURCE_NAME,
                SourceContact.source_contact_id == href
            ).first()

            if contact:
                contact.payload = normalized
                contact.source_updated_at = source_updated_at
                contact.etag = contact_info.get('etag')
                contact.updated_at = datetime.utcnow()
                logger.debug(f"Updated contact {href}")

    def _normalize_vcard(self, vcard: vobject.vCard) -> Dict[str, Any]:
        """
        Normalize vCard data to simplified JSON structure.

        Extracts commonly used fields (name, phone, email) from vCard format into
        a consistent JSON structure. Handles variability in how different CardDAV
        servers represent contact data (e.g., some use FN only, others use N with components).
        """
        display_name = ''
        given_name = ''
        family_name = ''

        # FN is formatted name (display name)
        if hasattr(vcard, 'fn'):
            display_name = vcard.fn.value

        # N is structured name (family, given, middle, prefix, suffix)
        if hasattr(vcard, 'n'):
            n = vcard.n.value
            family_name = n.family if hasattr(n, 'family') else ''
            given_name = n.given if hasattr(n, 'given') else ''

        # Extract all phone numbers with their types
        phones = []
        if hasattr(vcard, 'tel_list'):
            for tel in vcard.tel_list:
                phone_type = 'other'
                if hasattr(tel, 'type_param'):
                    phone_type = tel.type_param.lower() if isinstance(tel.type_param, str) else 'other'

                phones.append({
                    'value': tel.value,
                    'type': phone_type
                })

        # Extract all email addresses with their types
        emails = []
        if hasattr(vcard, 'email_list'):
            for email in vcard.email_list:
                email_type = 'other'
                if hasattr(email, 'type_param'):
                    email_type = email.type_param.lower() if isinstance(email.type_param, str) else 'other'

                emails.append({
                    'value': email.value,
                    'type': email_type
                })

        return {
            'display_name': display_name,
            'given_name': given_name,
            'family_name': family_name,
            'phones': phones,
            'emails': emails
        }

    def _update_sync_state(self, success: bool, error: Optional[str] = None):
        """
        Update sync state with status and error tracking.
        Maintains statistics for monitoring sync health and debugging failures.
        """
        sync_state = self.session.query(SyncState).filter(
            SyncState.source == self.SOURCE_NAME
        ).first()

        if not sync_state:
            sync_state = SyncState(source=self.SOURCE_NAME)
            self.session.add(sync_state)

        sync_state.last_sync_at = datetime.utcnow()

        if success:
            sync_state.last_success_at = datetime.utcnow()
            sync_state.error_count = 0
            sync_state.last_error = None
        else:
            sync_state.error_count += 1
            sync_state.last_error = error

        self.session.flush()
