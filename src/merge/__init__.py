"""
Merge package for combining contacts from multiple sources.

Implements collision resolution strategies when the same contact exists in multiple
providers. Uses latest-wins approach based on source timestamps, with configurable
source priority as tiebreaker. Produces canonical contacts that represent the best
available data for each unique phone number identity.
"""

from .merger import ContactMerger

__all__ = ['ContactMerger']
