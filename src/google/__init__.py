"""
Google People API integration package.

Exports client and sync classes for connecting to Google's People API (the successor
to the deprecated Contacts API). Supports OAuth 2.0 authentication and incremental
synchronization using sync tokens that track changes since last fetch.
"""

from .client import GoogleContactsClient
from .sync import GoogleContactsSync

__all__ = ['GoogleContactsClient', 'GoogleContactsSync']
