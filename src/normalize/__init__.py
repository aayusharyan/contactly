"""
Normalization package for contact data standardization.

Provides phone number normalization to E.164 international format and contact field
standardization across different source formats. E.164 normalization is critical for
reliable caller-id matching in PBX systems, ensuring "+1-415-555-1234", "4155551234",
and "(415) 555-1234" all become "+14155551234" for consistent lookups.
"""

from .normalizer import ContactNormalizer, PhoneNormalizer

__all__ = ['ContactNormalizer', 'PhoneNormalizer']
