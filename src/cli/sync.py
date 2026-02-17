"""
Manual sync script for one-time or on-demand contact synchronization.

Runs complete sync cycle: Google fetch, iCloud fetch, merge, publish to external DB.
Useful for testing, manual refreshes, or running as cron job instead of daemon.
Loads configuration from environment variables and handles errors gracefully with
detailed logging. Run with: python -m src.cli.sync
"""

import sys
import os
import logging
from dotenv import load_dotenv

from src.storage import get_session, init_db
from src.google import GoogleContactsClient, GoogleContactsSync
from src.icloud import ICloudCardDAVClient, ICloudContactsSync
from src.normalize import ContactNormalizer
from src.merge import ContactMerger
from src.db_writer import ContactsDatabaseWriter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """
    Load configuration from environment variables.
    Supports both new variable names and legacy PBX_* variables for backward compatibility.
    """
    config_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'config')
    env_file = os.path.join(config_dir, '.env')
    load_dotenv(env_file)

    return {
        'google_client_id': os.getenv('GOOGLE_CLIENT_ID'),
        'google_client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
        'google_refresh_token': os.getenv('GOOGLE_REFRESH_TOKEN'),
        'icloud_username': os.getenv('ICLOUD_USERNAME'),
        'icloud_password': os.getenv('ICLOUD_APP_PASSWORD'),
        'icloud_url': os.getenv('ICLOUD_CARDDAV_URL', 'https://contacts.icloud.com'),
        'external_db_url': (
            f"mysql+pymysql://{os.getenv('EXTERNAL_DB_USER', os.getenv('PBX_DB_USER'))}"
            f":{os.getenv('EXTERNAL_DB_PASSWORD', os.getenv('PBX_DB_PASSWORD'))}"
            f"@{os.getenv('EXTERNAL_DB_HOST', os.getenv('PBX_DB_HOST'))}"
            f":{os.getenv('EXTERNAL_DB_PORT', os.getenv('PBX_DB_PORT', '3306'))}"
            f"/{os.getenv('EXTERNAL_DB_NAME', os.getenv('PBX_DB_NAME'))}"
        ),
        'default_region': os.getenv('DEFAULT_PHONE_REGION', 'US')
    }


def run_sync():
    """
    Execute complete synchronization cycle.

    Five-phase process: (1) sync Google contacts, (2) sync iCloud contacts, (3) merge
    sources into canonical contacts using latest-wins, (4) write canonical to external
    MySQL, (5) verify write succeeded. Each phase logs progress and errors independently.
    """
    logger.info("=" * 60)
    logger.info("Starting contacts synchronization")
    logger.info("=" * 60)

    init_db()

    config = load_config()

    with get_session() as session:
        logger.info("\n[1/5] Syncing Google Contacts...")
        try:
            google_client = GoogleContactsClient(
                config['google_client_id'],
                config['google_client_secret'],
                config['google_refresh_token']
            )
            google_sync = GoogleContactsSync(google_client, session)
            google_stats = google_sync.sync()
            logger.info(f"Google sync stats: {google_stats}")
        except Exception as e:
            logger.error(f"Google sync failed: {e}", exc_info=True)

        logger.info("\n[2/5] Syncing iCloud Contacts...")
        try:
            icloud_client = ICloudCardDAVClient(
                config['icloud_username'],
                config['icloud_password'],
                config['icloud_url']
            )
            icloud_sync = ICloudContactsSync(icloud_client, session)
            icloud_stats = icloud_sync.sync()
            logger.info(f"iCloud sync stats: {icloud_stats}")
        except Exception as e:
            logger.error(f"iCloud sync failed: {e}", exc_info=True)

        logger.info("\n[3/5] Merging contacts...")
        try:
            normalizer = ContactNormalizer(default_region=config['default_region'])
            merger = ContactMerger(session, normalizer)
            merge_stats = merger.merge_all()
            logger.info(f"Merge stats: {merge_stats}")
        except Exception as e:
            logger.error(f"Merge failed: {e}", exc_info=True)
            return

        logger.info("\n[4/5] Writing to external database...")
        try:
            writer = ContactsDatabaseWriter(config['external_db_url'], session)
            write_stats = writer.write_contacts()
            logger.info(f"Database write stats: {write_stats}")
        except Exception as e:
            logger.error(f"Database write failed: {e}", exc_info=True)
            return

        logger.info("\n[5/5] Verifying write...")
        try:
            verification = writer.verify_write()
            logger.info(f"Verification: {verification}")
        except Exception as e:
            logger.error(f"Verification failed: {e}", exc_info=True)

    logger.info("\n" + "=" * 60)
    logger.info("Synchronization completed successfully!")
    logger.info("=" * 60)


if __name__ == '__main__':
    try:
        run_sync()
    except KeyboardInterrupt:
        logger.info("\nSync interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Sync failed with error: {e}", exc_info=True)
        sys.exit(1)
