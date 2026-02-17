"""
Contactly - Contact Data Normalization

Provides E.164 phone number conversion using Google's libphonenumber library and
contact field standardization. Handles phone numbers in various formats (local, international,
with/without country codes) and converts them to canonical E.164 format required for
reliable PBX caller-id lookups. Also standardizes contact name formats and validates emails.
"""

import logging
import re
from typing import Optional, List, Dict, Any
import phonenumbers
from phonenumbers import NumberParseException

logger = logging.getLogger(__name__)


class PhoneNormalizer:
    """
    Handles phone number normalization to E.164 format.

    Critical component for PBX integration - converts phone numbers from any format
    to international E.164 standard (+[country][area][number]). Without this, caller-id
    matching would fail when contacts use different formatting conventions.
    """

    def __init__(self, default_region: str = 'US'):
        """
        Initialize phone normalizer with default country.

        Default region is used when parsing numbers without explicit country code
        (e.g., "415-555-1234" gets interpreted as US number without region hint).

        Args:
            default_region: Default country code for parsing numbers without country prefix
        """
        self.default_region = default_region

    def normalize(self, phone: str, region: Optional[str] = None) -> Optional[str]:
        """
        Convert phone number to E.164 format.

        Uses libphonenumber for parsing and validation. Handles international prefixes,
        area codes, extensions, and formatting variations. Returns None for invalid
        numbers rather than raising exceptions, making error handling cleaner.

        Args:
            phone: Raw phone number string
            region: Country code for parsing (uses default if None)

        Returns:
            E.164 formatted number (e.g., +14155552671) or None if invalid
        """
        if not phone:
            return None

        phone = str(phone).strip()
        if not phone:
            return None

        region = region or self.default_region

        try:
            parsed = phonenumbers.parse(phone, region)

            if phonenumbers.is_valid_number(parsed):
                e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                return e164
            else:
                logger.debug(f"Invalid phone number: {phone}")
                return None

        except NumberParseException as e:
            logger.debug(f"Failed to parse phone number '{phone}': {e}")
            return None

    def normalize_multiple(self, phones: List[str], region: Optional[str] = None) -> List[str]:
        """
        Normalize multiple phone numbers, filtering out invalid ones.

        Automatically deduplicates results - if contact has same phone listed multiple
        times (e.g., both "mobile" and "iPhone"), only returns one E.164 representation.

        Args:
            phones: List of raw phone numbers
            region: Country code for parsing

        Returns:
            List of E.164 formatted numbers (duplicates removed)
        """
        normalized = []
        seen = set()

        for phone in phones:
            e164 = self.normalize(phone, region)
            if e164 and e164 not in seen:
                normalized.append(e164)
                seen.add(e164)

        return normalized


class ContactNormalizer:
    """
    Normalizes contact data from various sources to a unified format.

    Handles differences in how Google and iCloud represent contact data (field names,
    structures, missing data). Produces consistent output format regardless of source,
    simplifying downstream merge and export logic.
    """

    def __init__(self, default_region: str = 'US'):
        """
        Initialize contact normalizer.

        Args:
            default_region: Default country code for phone parsing
        """
        self.phone_normalizer = PhoneNormalizer(default_region)

    def normalize_contact(self, source_contact: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a source contact payload to canonical format.

        Extracts and standardizes display name, converts all phone numbers to E.164,
        validates emails, and produces consistent field structure. Primary phone is
        first valid number found (order depends on source provider's ordering).

        Args:
            source_contact: Raw contact data from source

        Returns:
            Normalized contact dictionary with standardized fields
        """
        display_name = self._extract_display_name(source_contact)

        phone_entries = source_contact.get('phones', [])
        raw_phones = [p['value'] for p in phone_entries if p.get('value')]
        normalized_phones = self.phone_normalizer.normalize_multiple(raw_phones)

        primary_phone = normalized_phones[0] if normalized_phones else None

        email_entries = source_contact.get('emails', [])
        emails = [e['value'] for e in email_entries if self._is_valid_email(e.get('value', ''))]

        return {
            'display_name': display_name,
            'given_name': source_contact.get('given_name', ''),
            'family_name': source_contact.get('family_name', ''),
            'phones': normalized_phones,
            'primary_phone': primary_phone,
            'emails': emails
        }

    def _extract_display_name(self, contact: Dict[str, Any]) -> str:
        """
        Extract the best display name from contact data.

        Tries display_name field first (usually most complete), then constructs from
        given/family names if needed. Falls back to 'Unknown' for contacts with no name
        data (rare but happens with badly formatted imports).
        """
        display_name = contact.get('display_name', '').strip()
        if display_name:
            return display_name

        given = contact.get('given_name', '').strip()
        family = contact.get('family_name', '').strip()

        if given and family:
            return f"{given} {family}"
        elif given:
            return given
        elif family:
            return family
        else:
            return 'Unknown'

    def _is_valid_email(self, email: str) -> bool:
        """
        Basic email validation using regex.

        Simple pattern match - not RFC 5322 compliant but catches obvious errors.
        Rejects empty strings, missing @ symbol, and malformed domains.

        Args:
            email: Email address to validate

        Returns:
            True if email appears valid
        """
        if not email:
            return False

        email = email.strip().lower()

        pattern = r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
        return bool(re.match(pattern, email))

    def extract_phone_identities(self, normalized_contact: Dict[str, Any]) -> List[tuple[str, str]]:
        """
        Extract (phone, display_name) tuples for PBX publishing.

        Each phone number becomes a separate identity for caller-id lookup. If contact
        has 3 phones, creates 3 separate lookup entries all with same display name. This
        ensures caller-id works regardless of which phone the person calls from.

        Args:
            normalized_contact: Normalized contact data

        Returns:
            List of (e164_phone, display_name) tuples
        """
        display_name = normalized_contact.get('display_name', 'Unknown')
        phones = normalized_contact.get('phones', [])

        return [(phone, display_name) for phone in phones]
