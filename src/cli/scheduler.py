"""
Contactly - Scheduled Sync Service

Runs contact synchronization on a recurring schedule (default: every 6 hours) using
APScheduler blocking scheduler. Implements exponential backoff on repeated failures to
avoid hammering APIs during outages. Suitable for running as systemd service or Docker
container. Performs initial sync on startup, then schedules recurring jobs.
"""

import os
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.internal_db import get_session, init_db
from src.google import GoogleContactsClient, GoogleContactsSync
from src.icloud import ICloudCardDAVClient, ICloudContactsSync
from src.normalize import ContactNormalizer
from src.merge import ContactMerger
from src.pbx_db import init_pbx_db, sync_to_pbx

logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

retry_count = 0
max_retries = int(os.getenv('SYNC_MAX_RETRIES', '5'))
backoff_base = int(os.getenv('SYNC_BACKOFF_BASE_SECONDS', '60'))


def load_config():
    """
    Load configuration from environment variables.
    Supports both new and legacy variable names for backward compatibility.
    """
    env_file = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
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
        'sync_interval_hours': int(os.getenv('SYNC_INTERVAL_HOURS', '6')),
        'default_region': os.getenv('DEFAULT_PHONE_REGION', 'US')
    }


def scheduled_sync_job():
    """
    Job function executed by scheduler.

    Runs complete sync cycle with error handling. Tracks consecutive failures and
    implements exponential backoff (60s, 120s, 240s, ...) after max_retries reached
    to avoid overwhelming services during prolonged outages. Resets retry count on success.
    """
    global retry_count

    logger.info(f"Starting scheduled sync at {datetime.now()}")

    try:
        config = load_config()

        with get_session() as session:
            google_client = GoogleContactsClient(
                config['google_client_id'],
                config['google_client_secret'],
                config['google_refresh_token']
            )
            google_sync = GoogleContactsSync(google_client, session)
            google_stats = google_sync.sync()
            logger.info(f"Google sync: {google_stats}")

            icloud_client = ICloudCardDAVClient(
                config['icloud_username'],
                config['icloud_password'],
                config['icloud_url']
            )
            icloud_sync = ICloudContactsSync(icloud_client, session)
            icloud_stats = icloud_sync.sync()
            logger.info(f"iCloud sync: {icloud_stats}")

            normalizer = ContactNormalizer(default_region=config['default_region'])
            merger = ContactMerger(session, normalizer)
            merge_stats = merger.merge_all()
            logger.info(f"Merge: {merge_stats}")

            write_stats = sync_to_pbx(session, config['external_db_url'])
            logger.info(f"Database write: {write_stats}")

        retry_count = 0
        logger.info("Scheduled sync completed successfully")

    except Exception as e:
        retry_count += 1
        logger.error(f"Sync failed (attempt {retry_count}/{max_retries}): {e}", exc_info=True)

        if retry_count >= max_retries:
            backoff_seconds = backoff_base * (2 ** (retry_count - 1))
            logger.warning(f"Max retries reached, backing off for {backoff_seconds} seconds")
            time.sleep(backoff_seconds)
            retry_count = 0


def main():
    """
    Initialize scheduler and run sync service.
    Sets up database, performs initial sync, then starts recurring schedule.
    Blocks until Ctrl+C or system signal received.
    """
    logger.info("=" * 60)
    logger.info("Contactly - Scheduled Sync Service")
    logger.info("=" * 60)

    init_db()

    config = load_config()
    init_pbx_db(config['external_db_url'])
    sync_interval = config['sync_interval_hours']

    logger.info(f"Sync interval: {sync_interval} hours")
    logger.info(f"Max retries: {max_retries}")
    logger.info(f"Backoff base: {backoff_base} seconds")

    logger.info("\nRunning initial sync...")
    scheduled_sync_job()

    scheduler = BlockingScheduler()

    trigger = IntervalTrigger(hours=sync_interval)
    scheduler.add_job(
        scheduled_sync_job,
        trigger=trigger,
        id='contacts_sync',
        name='Contacts Sync Job',
        replace_existing=True
    )

    logger.info(f"\nScheduler started. Next sync in {sync_interval} hours.")
    logger.info("Press Ctrl+C to exit.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("\nShutting down scheduler...")
        scheduler.shutdown()
        logger.info("Scheduler stopped.")


if __name__ == '__main__':
    main()
