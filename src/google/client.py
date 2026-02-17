"""
Contactly - Google People API Client

Handles OAuth 2.0 authentication using environment variables, automatic token
refresh, and API requests to Google People API v1. Implements sync cursor support
for efficient incremental updates that only fetch contacts changed since last sync.
Manages pagination automatically for large contact lists.
"""

import os
import json
from typing import Optional, List, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Read-only access to contacts
SCOPES = ['https://www.googleapis.com/auth/contacts.readonly']


class GoogleContactsClient:
    """
    Client for interacting with Google People API.

    Manages OAuth 2.0 authentication using environment variables with automatic token
    refresh. Provides methods for fetching contacts with pagination and incremental
    sync support via sync cursors (valid for 7 days). Note: "cursor" here refers to
    a sync checkpoint/bookmark, not an authentication token.
    """

    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        """
        Initialize the Google Contacts client using OAuth credentials.

        Credentials are provided via environment variables. Token refresh happens
        automatically when the access token expires.

        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
            refresh_token: Google OAuth refresh token
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """
        Authenticate with Google OAuth using credentials from environment variables.

        Builds credentials object from client ID, client secret, and refresh token.
        Token refresh happens automatically when the token expires.
        """
        # Build credentials from environment variables
        creds = Credentials(
            token=None,  # Will be automatically obtained via refresh
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=SCOPES
        )

        # Get fresh access token using refresh token
        creds.refresh(Request())

        self.service = build('people', 'v1', credentials=creds)

    def list_connections(
        self,
        sync_token: Optional[str] = None,
        page_size: int = 1000,
        page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch contacts from Google People API with optional incremental sync.

        Supports two modes: full sync (sync_token=None) fetches all contacts,
        incremental sync (with cursor) fetches only changes. Sync cursors expire
        after 7 days, requiring fallback to full sync. Returns pagination tokens
        for handling large contact lists.

        Args:
            sync_token: Sync cursor for incremental sync (None for full sync).
                       Named sync_token to match Google's API parameter.
            page_size: Number of contacts per page
            page_token: Token for pagination

        Returns:
            Dictionary containing connections, next page token, and new sync cursor
        """
        try:
            request_params = {
                'resourceName': 'people/me',
                'pageSize': page_size,
                'personFields': 'names,phoneNumbers,emailAddresses,metadata'
            }

            # Configure for incremental or full sync
            if sync_token:
                request_params['requestSyncToken'] = True
                request_params['syncToken'] = sync_token
            else:
                request_params['requestSyncToken'] = True
                # Sort by modification time for efficient initial sync
                request_params['sortOrder'] = 'LAST_MODIFIED_DESCENDING'

            if page_token:
                request_params['pageToken'] = page_token

            result = self.service.people().connections().list(**request_params).execute()

            return {
                'connections': result.get('connections', []),
                'nextPageToken': result.get('nextPageToken'),
                'nextSyncToken': result.get('nextSyncToken'),
                'totalItems': result.get('totalItems', 0)
            }

        except HttpError as e:
            # Handle specific HTTP error codes with meaningful exceptions
            if e.resp.status == 410:
                raise SyncTokenExpiredError("Sync token expired, full sync required")
            elif e.resp.status == 429:
                raise RateLimitError("Rate limit exceeded")
            else:
                raise

    def fetch_all_connections(self, sync_token: Optional[str] = None) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Fetch all contacts, handling pagination automatically.

        Iterates through all pages until no nextPageToken is returned. Useful for
        simplifying caller code that doesn't need granular pagination control.

        Args:
            sync_token: Sync cursor for incremental sync (parameter named to match Google's API)

        Returns:
            Tuple of (list of all connections, new sync cursor)
        """
        all_connections = []
        page_token = None
        new_sync_token = None

        # Keep fetching pages until no more pages remain
        while True:
            result = self.list_connections(
                sync_token=sync_token,
                page_token=page_token
            )

            connections = result['connections']
            if connections:
                all_connections.extend(connections)

            page_token = result.get('nextPageToken')
            new_sync_token = result.get('nextSyncToken')

            if not page_token:
                break

        return all_connections, new_sync_token


class SyncTokenExpiredError(Exception):
    """Raised when Google sync cursor has expired (typically after 7 days)."""
    pass


class RateLimitError(Exception):
    """Raised when Google API rate limit is exceeded."""
    pass
