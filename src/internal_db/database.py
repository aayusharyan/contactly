"""
Contactly - Database Session Management

Provides context managers and factory functions for SQLAlchemy database sessions.
Handles connection pooling, transaction management, and automatic rollback on errors.
Loads database configuration from environment variables with sensible defaults.
Includes simple SQL-file-based migration system for automatic schema evolution.
"""

import os
import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

from .schema import Base

logger = logging.getLogger(__name__)

# Load environment variables from .env in project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

LOCAL_DB_PATH = os.getenv('LOCAL_DB_PATH', 'sqlite:///contacts_sync.db')

# Create engine with connection health checks (pool_pre_ping)
engine = create_engine(LOCAL_DB_PATH, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_session() -> Session:
    """
    Context manager for database sessions.

    Automatically commits on success or rolls back on exception, ensuring
    data consistency. Always closes session to prevent connection leaks.
    Usage: with get_session() as session: ...
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """
    Initialize internal database by running all SQL migrations.

    Executes all .sql files from migrations/internal_db/ directory in sorted order.
    Migrations are idempotent (use IF NOT EXISTS, etc.) so safe to run repeatedly.
    Creates canonical_contact, source_contact, and sync_state tables with indexes.
    """
    logger.info("Initializing internal database...")

    migrations_dir = Path(__file__).parent.parent.parent / 'migrations' / 'internal_db'

    if not migrations_dir.exists():
        logger.info("No internal_db migrations directory found, skipping migrations")
        return

    migration_files = sorted(migrations_dir.glob('*.sql'))

    if not migration_files:
        logger.info("No internal_db migration files found")
        return

    for migration_file in migration_files:
        logger.info(f"Running internal_db migration: {migration_file.name}")
        _execute_sql_file(migration_file)
        logger.info(f"✓ Internal_db migration completed: {migration_file.name}")

    logger.info("Internal database initialization complete")


def _execute_sql_file(sql_file_path: Path):
    """
    Execute SQL statements from a file against SQLite database.

    Reads SQL file and executes all statements. Migrations should be idempotent
    using IF NOT EXISTS, IF EXISTS, etc. for safe re-execution. Splits on semicolons
    to handle multiple statements per file.

    Args:
        sql_file_path: Path to SQL file to execute
    """
    db_path = LOCAL_DB_PATH.replace('sqlite:///', '')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        with open(sql_file_path, 'r') as f:
            sql_content = f.read()

        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

        for statement in statements:
            if statement.startswith('--'):
                continue
            cursor.execute(statement)

        conn.commit()

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to execute SQL file {sql_file_path.name}: {e}")
        raise
    finally:
        conn.close()
