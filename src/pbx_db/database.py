"""
Contactly - PBX Database Management

Handles setup and schema evolution for external MySQL database that PBX systems
query for caller-id name lookups. Executes SQL migrations from migrations/pbx_db/
directory in sorted order. All migrations are idempotent (use IF NOT EXISTS) for
safe repeated execution. Mirrors the internal_db initialization pattern for consistency.
Uses ORM models from schema.py as source of truth for table structure.

Provides simple function-based API for syncing canonical contacts to PBX database,
matching the internal_db pattern (no class wrappers, just functions).
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from .schema import Base, PbxCnam

logger = logging.getLogger(__name__)

# Load environment variables from .env in project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))


def get_pbx_db_url() -> str:
    """
    Build MySQL connection URL from environment variables.

    Checks both EXTERNAL_DB_* and PBX_DB_* prefixes for backwards compatibility.
    Falls back to PBX_DB_* if EXTERNAL_DB_* variables are not set.

    Returns:
        MySQL connection string in format: mysql+pymysql://user:pass@host:port/db
    """
    return (
        f"mysql+pymysql://{os.getenv('EXTERNAL_DB_USER', os.getenv('PBX_DB_USER'))}"
        f":{os.getenv('EXTERNAL_DB_PASSWORD', os.getenv('PBX_DB_PASSWORD'))}"
        f"@{os.getenv('EXTERNAL_DB_HOST', os.getenv('PBX_DB_HOST'))}"
        f":{os.getenv('EXTERNAL_DB_PORT', os.getenv('PBX_DB_PORT', '3306'))}"
        f"/{os.getenv('EXTERNAL_DB_NAME', os.getenv('PBX_DB_NAME'))}"
    )


def init_pbx_db(external_db_url: str = None):
    """
    Initialize PBX database by running all SQL migrations.

    Executes all .sql files from migrations/pbx_db/ directory in sorted order.
    Migrations are idempotent (use IF NOT EXISTS, etc.) so safe to run repeatedly.
    Creates pbx_cnam table and associated indexes for fast caller-id lookups.

    Uses ORM models from schema.py as the source of truth. Migration SQL files
    should match the ORM definitions exactly for consistency.

    Args:
        external_db_url: MySQL connection string. If None, builds from env vars.
    """
    if external_db_url is None:
        external_db_url = get_pbx_db_url()

    logger.info("Initializing PBX database...")

    migrations_dir = Path(__file__).parent.parent.parent / 'migrations' / 'pbx_db'

    if not migrations_dir.exists():
        logger.info("No PBX migrations directory found, skipping migrations")
        return

    migration_files = sorted(migrations_dir.glob('*.sql'))

    if not migration_files:
        logger.info("No PBX migration files found")
        return

    engine = create_engine(external_db_url, pool_pre_ping=True)

    for migration_file in migration_files:
        logger.info(f"Running PBX migration: {migration_file.name}")
        _execute_sql_file(engine, migration_file)
        logger.info(f"✓ PBX migration completed: {migration_file.name}")

    logger.info("PBX database initialization complete")


def _execute_sql_file(engine, sql_file_path: Path):
    """
    Execute SQL statements from a file against MySQL database.

    Reads SQL file and executes all statements. Migrations should be idempotent
    using IF NOT EXISTS, IF EXISTS, etc. for safe re-execution. Splits on semicolons
    to handle multiple statements per file.

    Args:
        engine: SQLAlchemy engine for MySQL connection
        sql_file_path: Path to SQL file to execute
    """
    with engine.connect() as conn:
        try:
            with open(sql_file_path, 'r') as f:
                sql_content = f.read()

            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

            for statement in statements:
                if statement.startswith('--'):
                    continue
                conn.execute(text(statement))

            conn.commit()

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to execute SQL file {sql_file_path.name}: {e}")
            raise


def sync_to_pbx(local_session: Session, external_db_url: str = None) -> Dict[str, Any]:
    """
    Sync canonical contacts to external PBX database.

    Reads canonical contacts from local session and syncs them to external MySQL database.
    Performs three-way comparison (canonical, existing external, diff) to determine
    inserts/updates/deletes. All operations in single transaction for consistency.

    Args:
        local_session: Session to canonical contacts database
        external_db_url: MySQL connection string. If None, builds from env vars.

    Returns:
        Dictionary with sync statistics (inserted, updated, deleted, errors)
    """
    from ..internal_db.schema import CanonicalContact

    if external_db_url is None:
        external_db_url = get_pbx_db_url()

    stats = {
        'inserted': 0,
        'updated': 0,
        'deleted': 0,
        'errors': 0
    }

    logger.info("Starting PBX database sync")

    try:
        external_engine = create_engine(external_db_url, pool_pre_ping=True)
        canonical_contacts = local_session.query(CanonicalContact).all()
        canonical_phones = {c.best_e164: c for c in canonical_contacts}

        with external_engine.connect() as conn:
            # Find and delete stale entries (exist in external but not in canonical)
            existing_result = conn.execute(select(PbxCnam.e164))
            existing_phones = {row[0] for row in existing_result}

            to_delete = existing_phones - set(canonical_phones.keys())
            for phone in to_delete:
                conn.execute(
                    PbxCnam.__table__.delete().where(PbxCnam.e164 == phone)
                )
                stats['deleted'] += 1
                logger.debug(f"Deleted PBX entry for {phone}")

            # Insert or update each canonical contact
            for phone, contact in canonical_phones.items():
                try:
                    winning_source = contact.extra_data.get('winning_source', 'unknown') if contact.extra_data else 'unknown'

                    # Check if record already exists
                    existing = conn.execute(
                        select(PbxCnam).where(PbxCnam.e164 == phone)
                    ).first()

                    if existing:
                        # Update existing record
                        conn.execute(
                            PbxCnam.__table__.update()
                            .where(PbxCnam.e164 == phone)
                            .values(
                                display_name=contact.best_display_name,
                                updated_at=contact.canonical_updated_at,
                                source=winning_source
                            )
                        )
                        stats['updated'] += 1
                        logger.debug(f"Updated PBX entry for {phone}")
                    else:
                        # Insert new record
                        conn.execute(
                            PbxCnam.__table__.insert().values(
                                e164=phone,
                                display_name=contact.best_display_name,
                                updated_at=contact.canonical_updated_at,
                                source=winning_source
                            )
                        )
                        stats['inserted'] += 1
                        logger.debug(f"Inserted PBX entry for {phone}")

                except Exception as e:
                    logger.error(f"Failed to sync contact {phone}: {e}")
                    stats['errors'] += 1

            # Commit transaction
            conn.commit()

        logger.info(f"PBX database sync completed: {stats}")

    except Exception as e:
        logger.error(f"PBX database sync failed: {e}")
        raise

    return stats


def verify_pbx_sync(local_session: Session, external_db_url: str = None) -> Dict[str, Any]:
    """
    Verify PBX database sync by comparing counts and sampling records.

    Sanity check after sync operation - ensures canonical and external databases
    are in sync. Count mismatch indicates sync failure or transaction rollback.

    Args:
        local_session: Session to canonical contacts database
        external_db_url: MySQL connection string. If None, builds from env vars.

    Returns:
        Dictionary with verification results (counts, match status, samples)
    """
    from ..internal_db.schema import CanonicalContact

    if external_db_url is None:
        external_db_url = get_pbx_db_url()

    canonical_count = local_session.query(CanonicalContact).count()

    external_engine = create_engine(external_db_url, pool_pre_ping=True)
    with external_engine.connect() as conn:
        result = conn.execute(select(PbxCnam))
        external_contacts = result.fetchall()
        external_count = len(external_contacts)

    verification = {
        'canonical_count': canonical_count,
        'external_count': external_count,
        'match': canonical_count == external_count,
        'sample': [
            {
                'e164': row[0],
                'display_name': row[1],
                'updated_at': row[2],
                'source': row[3]
            }
            for row in external_contacts[:5]
        ]
    }

    logger.info(f"PBX verification: {verification['canonical_count']} canonical, {verification['external_count']} external")
    return verification
