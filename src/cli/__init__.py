"""
Command-line interface entry points.

This module contains all CLI commands and entry points for the application:
- scheduler: Long-running daemon for scheduled syncs
- sync: One-time manual sync execution

Note: Database initialization happens automatically when running sync or scheduler.
OAuth token must be generated externally and mounted into the container.
"""
