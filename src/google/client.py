"""
Google People API client for contact synchronization.

Handles OAuth 2.0 authentication flow, token management (refresh, storage), and
API requests to Google People API v1. Implements sync cursor support for efficient
incremental updates that only fetch contacts changed since last sync. Manages
pagination automatically for large contact lists.
"""

import os
import pickle
from typing import Optional, List, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Read-only access to contacts - follows principle of least privilege
SCOPES = ['https://www.googleapis.com/auth/contacts.readonly']


class GoogleContactsClient:
    """
    Client for interacting with Google People API.

    Manages complete OAuth 2.0 lifecycle including initial authorization, token storage,
    and automatic refresh. Provides methods for fetching contacts with pagination and
    incremental sync support via sync cursors (valid for 7 days). Note: "cursor" here
    refers to a sync checkpoint/bookmark, not an authentication token.
    """

    def __init__(self, credentials_path: str, token_path: str):
        """
        Initialize the Google Contacts client.

        Creates OAuth credentials from client secrets file and stored token.
        If token doesn't exist or is invalid, initiates interactive OAuth flow.

        Args:
            credentials_path: Path to OAuth credentials JSON file
            token_path: Path to store/load OAuth token
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """
        Authenticate with Google OAuth and build the service client.

        Handles three scenarios: load existing valid token, refresh expired token,
        or run interactive authorization flow for new user. Tokens are persisted to
        disk to avoid repeated authorization prompts.
        """
        creds = None

        # Try to load existing token
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)

        # Refresh expired token or run new authorization flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Interactive OAuth flow - opens browser or provides URL
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Persist token for future use
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)

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
