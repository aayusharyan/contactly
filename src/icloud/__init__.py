"""
iCloud CardDAV integration package.

Exports client and sync classes for connecting to iCloud's CardDAV service
and synchronizing contacts using the industry-standard CardDAV protocol with
ETag-based change detection for efficient incremental updates.
"""

from .client import ICloudCardDAVClient
from .sync import ICloudContactsSync

__all__ = ['ICloudCardDAVClient', 'ICloudContactsSync']
