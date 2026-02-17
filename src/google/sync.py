"""
Google contacts synchronization coordinator.

Orchestrates the complete sync workflow: fetch contacts from Google People API using
sync cursors for incremental updates, process contact data including deletions, and
store in local database. Implements automatic fallback to full sync when cursors expire
(after 7 days), with robust error handling for rate limits and transient failures.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from .client import GoogleContactsClient, SyncTokenExpiredError, RateLimitError
from ..storage.schema import SourceContact, SyncState

logger = logging.getLogger(__name__)


class GoogleContactsSync:
    """
    Manages synchronization of contacts from Google People API.

    Coordinates sync cursor management, contact processing, and error recovery.
    Handles incremental updates efficiently by storing sync cursors between runs,
    falling back to full sync only when necessary.
    """

    SOURCE_NAME = 'google'

    def __init__(self, client: GoogleContactsClient, session: Session):
        """
        Initialize sync coordinator.

        Args:
            client: Authenticated Google API client
            session: Database session for storing contacts
        """
        self.client = client
        self.session = session

    def sync(self) -> Dict[str, Any]:
        """
        Perform contact synchronization from Google.

        Attempts incremental sync first using stored sync cursor. If cursor expired (410 error),
        automatically falls back to full sync. Processes all contacts including deletions
        (marked by metadata.deleted flag). Returns detailed statistics for monitoring.

        Returns:
            Dictionary with sync statistics (added, updated, deleted, errors)
        """
        stats = {
            'added': 0,
            'updated': 0,
            'deleted': 0,
            'errors': 0,
            'sync_type': 'full'
        }

        sync_state = self._get_sync_state()
        sync_cursor = sync_state.sync_cursor if sync_state else None

        try:
            if sync_cursor:
                logger.info("Attempting incremental sync with cursor")
                stats['sync_type'] = 'incremental'
            else:
                logger.info("Starting full sync (no sync cursor)")

            # Fetch contacts from Google People API (sync_token param is Google's naming)
            connections, new_sync_cursor = self.client.fetch_all_connections(sync_cursor)

            logger.info(f"Fetched {len(connections)} contacts from Google")

            # Process each connection (add/update/delete)
            for connection in connections:
                try:
                    self._process_connection(connection, stats)
                except Exception as e:
                    logger.error(f"Error processing connection {connection.get('resourceName')}: {e}")
                    stats['errors'] += 1

            # Save new sync cursor for next incremental sync
            self._update_sync_state(new_sync_cursor, success=True)

            self.session.commit()
            logger.info(f"Google sync completed: {stats}")

        except SyncTokenExpiredError:
            # Cursor expired (after 7 days) - clear and retry with full sync
            logger.warning("Sync cursor expired, performing full sync")
            self.session.rollback()
            self._clear_sync_cursor()
            return self.sync()

        except RateLimitError:
            # Rate limit hit - save state and propagate for retry later
            logger.error("Rate limit exceeded, will retry later")
            self._update_sync_state(sync_cursor, success=False, error="Rate limit exceeded")
            raise

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            self._update_sync_state(sync_cursor, success=False, error=str(e))
            raise

        return stats

    def _process_connection(self, connection: Dict[str, Any], stats: Dict[str, Any]):
        """
        Process a single contact from Google API.

        Handles three cases: new contact (insert), existing contact (update), and
        deleted contact (remove). Google marks deletions with metadata.deleted=true
        rather than omitting them from results, enabling proper incremental sync.
        """
        resource_name = connection.get('resourceName')
        if not resource_name:
            logger.warning("Connection missing resourceName, skipping")
            return

        metadata = connection.get('metadata', {})
        deleted = metadata.get('deleted', False)

        # Check if contact already exists in local database
        existing = self.session.query(SourceContact).filter(
            SourceContact.source == self.SOURCE_NAME,
            SourceContact.source_contact_id == resource_name
        ).first()

        # Handle deletion case
        if deleted:
            if existing:
                self.session.delete(existing)
                stats['deleted'] += 1
                logger.debug(f"Deleted contact {resource_name}")
            return

        # Extract timestamp from metadata sources
        update_time_str = metadata.get('sources', [{}])[0].get('updateTime')
        source_updated_at = None
        if update_time_str:
            try:
                source_updated_at = datetime.fromisoformat(update_time_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass

        normalized_payload = self._normalize_connection(connection)

        if existing:
            existing.payload = normalized_payload
            existing.source_updated_at = source_updated_at
            existing.updated_at = datetime.utcnow()
            stats['updated'] += 1
            logger.debug(f"Updated contact {resource_name}")
        else:
            new_contact = SourceContact(
                canonical_id=f"google_{resource_name.split('/')[-1]}",
                source=self.SOURCE_NAME,
                source_contact_id=resource_name,
                payload=normalized_payload,
                source_updated_at=source_updated_at
            )
            self.session.add(new_contact)
            stats['added'] += 1
            logger.debug(f"Added contact {resource_name}")

    def _normalize_connection(self, connection: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Google contact data to a simplified JSON structure.

        Extracts key fields from Google's complex nested structure into flat format
        for storage. Handles missing fields gracefully since not all contacts have
        all fields populated.
        """
        names = connection.get('names', [])
        phones = connection.get('phoneNumbers', [])
        emails = connection.get('emailAddresses', [])

        primary_name = names[0] if names else {}

        return {
            'display_name': primary_name.get('displayName', ''),
            'given_name': primary_name.get('givenName', ''),
            'family_name': primary_name.get('familyName', ''),
            'phones': [
                {
                    'value': p.get('value', ''),
                    'type': p.get('type', 'other')
                }
                for p in phones
            ],
            'emails': [
                {
                    'value': e.get('value', ''),
                    'type': e.get('type', 'other')
                }
                for e in emails
            ]
        }

    def _get_sync_state(self) -> Optional[SyncState]:
        """
        Retrieve the current sync state for Google source.
        Contains sync token and error tracking for resumable operations.
        """
        return self.session.query(SyncState).filter(
            SyncState.source == self.SOURCE_NAME
        ).first()

    def _update_sync_state(self, sync_cursor: Optional[str], success: bool, error: Optional[str] = None):
        """
        Update sync state with new cursor and status.
        Tracks sync cursors, timestamps, and error counts for monitoring and debugging.
        """
        sync_state = self._get_sync_state()

        if not sync_state:
            sync_state = SyncState(source=self.SOURCE_NAME)
            self.session.add(sync_state)

        sync_state.sync_cursor = sync_cursor
        sync_state.last_sync_at = datetime.utcnow()

        if success:
            sync_state.last_success_at = datetime.utcnow()
            sync_state.error_count = 0
            sync_state.last_error = None
        else:
            sync_state.error_count += 1
            sync_state.last_error = error

        self.session.flush()

    def _clear_sync_cursor(self):
        """
        Clear the sync cursor to force a full sync next time.
        Used when cursor expires or becomes invalid, ensuring recovery from sync errors.
        """
        sync_state = self._get_sync_state()
        if sync_state:
            sync_state.sync_cursor = None
            self.session.commit()
