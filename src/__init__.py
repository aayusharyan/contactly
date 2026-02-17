"""
Main package initialization module.

This module coordinates bidirectional contact synchronization between Google Contacts,
iCloud CardDAV, and an external PBX database. It implements incremental sync with
ETag/sync-token tracking, contact merging with conflict resolution, and maintains
a canonical contact database for unified caller ID lookups.
"""

__version__ = '1.0.0'
__author__ = 'contactly'
