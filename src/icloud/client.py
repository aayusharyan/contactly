"""
Contactly - iCloud CardDAV Client

Implements the CardDAV protocol (RFC 6352) to communicate with Apple's iCloud
contacts service. Handles server discovery, contact enumeration with ETags for
change tracking, and vCard parsing. Uses PROPFIND WebDAV requests to efficiently
query contact metadata before fetching full vCard data.
"""

import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin
import requests
from requests.auth import HTTPBasicAuth
from lxml import etree
import vobject

logger = logging.getLogger(__name__)

# WebDAV and CardDAV namespace definitions for XML parsing
DAV_NAMESPACES = {
    'D': 'DAV:',
    'C': 'urn:ietf:params:xml:ns:carddav'
}


class ICloudCardDAVClient:
    """
    CardDAV protocol client for Apple iCloud contacts.

    Manages authentication, server discovery, and contact retrieval from iCloud's
    CardDAV endpoint. Supports ETag-based change detection for efficient incremental
    synchronization without downloading unchanged contacts.
    """

    def __init__(self, username: str, app_password: str, base_url: str = "https://contacts.icloud.com"):
        """
        Initialize CardDAV client with credentials.
        Note: Regular Apple ID passwords won't work - must use app-specific password
        generated from appleid.apple.com security settings.

        Args:
            username: Apple ID email
            app_password: App-specific password from Apple ID settings
            base_url: CardDAV server base URL
        """
        self.username = username
        self.app_password = app_password
        self.base_url = base_url
        self.auth = HTTPBasicAuth(username, app_password)
        self.addressbook_url = None
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            'User-Agent': 'ContactsSync/1.0',
            'Content-Type': 'application/xml; charset=utf-8'
        })

    def discover_addressbook(self) -> str:
        """
        Discover addressbook collection URL using CardDAV service discovery.

        Implements two-step discovery: first find principal's addressbook-home-set,
        then query that location to find the actual addressbook collection with
        contacts. This follows the CardDAV specification for multi-tenant servers.

        Returns:
            Addressbook collection URL
        """
        if self.addressbook_url:
            return self.addressbook_url

        principal_url = f"{self.base_url}/principal/"

        # XML request to find addressbook home set location
        propfind_body = """<?xml version="1.0" encoding="UTF-8"?>
<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:carddav">
  <D:prop>
    <C:addressbook-home-set/>
  </D:prop>
</D:propfind>"""

        response = self.session.request(
            'PROPFIND',
            principal_url,
            data=propfind_body.encode('utf-8'),
            headers={'Depth': '0'}
        )
        response.raise_for_status()

        # Parse XML response to extract addressbook home URL
        tree = etree.fromstring(response.content)
        addressbook_home = tree.find('.//C:addressbook-home-set/D:href', DAV_NAMESPACES)

        if addressbook_home is None:
            raise ValueError("Could not discover addressbook home")

        addressbook_home_url = addressbook_home.text

        # Second query: find actual addressbook collection within home
        response = self.session.request(
            'PROPFIND',
            urljoin(self.base_url, addressbook_home_url),
            data=propfind_body.encode('utf-8'),
            headers={'Depth': '1'}
        )
        response.raise_for_status()

        # Find the response element that has resourcetype of addressbook
        tree = etree.fromstring(response.content)
        for response_elem in tree.findall('.//D:response', DAV_NAMESPACES):
            resourcetype = response_elem.find('.//D:resourcetype', DAV_NAMESPACES)
            if resourcetype is not None and resourcetype.find('C:addressbook', DAV_NAMESPACES) is not None:
                href = response_elem.find('D:href', DAV_NAMESPACES)
                if href is not None:
                    self.addressbook_url = urljoin(self.base_url, href.text)
                    logger.info(f"Discovered addressbook URL: {self.addressbook_url}")
                    return self.addressbook_url

        raise ValueError("Could not find addressbook collection")

    def list_contacts_with_etags(self) -> List[Dict[str, str]]:
        """
        List all contacts with their ETags using PROPFIND.

        ETags are unique identifiers that change whenever a contact is modified.
        By comparing ETags from the server with locally stored ETags, we can determine
        which contacts have changed and only fetch those, dramatically reducing API calls.

        Returns:
            List of dictionaries with 'href', 'etag', 'last_modified'
        """
        if not self.addressbook_url:
            self.discover_addressbook()

        # Request ETag and last-modified for all resources in addressbook
        propfind_body = """<?xml version="1.0" encoding="UTF-8"?>
<D:propfind xmlns:D="DAV:">
  <D:prop>
    <D:getetag/>
    <D:getlastmodified/>
  </D:prop>
</D:propfind>"""

        response = self.session.request(
            'PROPFIND',
            self.addressbook_url,
            data=propfind_body.encode('utf-8'),
            headers={'Depth': '1'}
        )
        response.raise_for_status()

        tree = etree.fromstring(response.content)
        contacts = []

        # Parse each response element to extract contact metadata
        for response_elem in tree.findall('.//D:response', DAV_NAMESPACES):
            href_elem = response_elem.find('D:href', DAV_NAMESPACES)
            if href_elem is None:
                continue

            href = href_elem.text

            # Skip the addressbook itself and non-vCard resources
            if href == self.addressbook_url or not href.endswith('.vcf'):
                continue

            etag_elem = response_elem.find('.//D:getetag', DAV_NAMESPACES)
            lastmod_elem = response_elem.find('.//D:getlastmodified', DAV_NAMESPACES)

            contact_info = {
                'href': href,
                'etag': etag_elem.text.strip('"') if etag_elem is not None else None,
                'last_modified': lastmod_elem.text if lastmod_elem is not None else None
            }
            contacts.append(contact_info)

        logger.info(f"Found {len(contacts)} contacts in addressbook")
        return contacts

    def fetch_vcard(self, href: str) -> Optional[vobject.vCard]:
        """
        Fetch and parse a single vCard from the server.
        vCard is the standard format (RFC 6350) for electronic business cards.

        Args:
            href: Contact resource URL

        Returns:
            Parsed vCard object or None if fetch fails
        """
        url = urljoin(self.base_url, href)

        try:
            response = self.session.get(url)
            response.raise_for_status()

            vcard = vobject.readOne(response.text)
            return vcard

        except Exception as e:
            logger.error(f"Failed to fetch vCard from {href}: {e}")
            return None

    def fetch_multiple_vcards(self, hrefs: List[str]) -> List[Tuple[str, Optional[vobject.vCard]]]:
        """
        Fetch multiple vCards in sequence with basic rate limiting.

        Adds small delays every 10 requests to avoid overwhelming the server or
        triggering rate limits. For production use with many contacts, consider
        implementing multiget-report for batch fetching.

        Args:
            hrefs: List of contact resource URLs

        Returns:
            List of tuples (href, vCard object or None)
        """
        import time
        results = []

        for i, href in enumerate(hrefs):
            vcard = self.fetch_vcard(href)
            results.append((href, vcard))

            # Brief pause every 10 requests to avoid rate limiting
            if (i + 1) % 10 == 0:
                time.sleep(0.5)

        return results
