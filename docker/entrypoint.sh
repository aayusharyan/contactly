#!/bin/bash
# Docker container entrypoint script that validates configuration before starting the sync service.
# Validates required environment variables for iCloud, Google OAuth, and PBX database connectivity.
# Provides helpful error messages when credentials are missing or incomplete.
# Logs configuration summary before starting the scheduler.

# Exit immediately if any command fails
set -e

echo "========================================================================"
echo "Contactly - Starting"
echo "Syncs Google and iCloud contacts with PBX database for caller ID"
echo "Developed by Aayush Sinha (https://yush.dev)"
echo "========================================================================"

mkdir -p /app/data

# Check if Google OAuth credentials are fully configured.
# All three variables must be present for Google sync to work.
GOOGLE_CONFIGURED=false
if [ -n "$GOOGLE_CLIENT_ID" ] && [ -n "$GOOGLE_CLIENT_SECRET" ] && [ -n "$GOOGLE_REFRESH_TOKEN" ]; then
    GOOGLE_CONFIGURED=true
    echo "✓ Google OAuth credentials configured"
else
    if [ -n "$GOOGLE_CLIENT_ID" ] || [ -n "$GOOGLE_CLIENT_SECRET" ] || [ -n "$GOOGLE_REFRESH_TOKEN" ]; then
        echo ""
        echo "========================================================================"
        echo "ERROR: Incomplete Google OAuth configuration!"
        echo "========================================================================"
        echo ""
        echo "All three environment variables are required:"
        echo "  - GOOGLE_CLIENT_ID"
        echo "  - GOOGLE_CLIENT_SECRET"
        echo "  - GOOGLE_REFRESH_TOKEN"
        echo ""
        echo "To generate these values, follow the setup guide:"
        echo "  https://github.com/aayusharyan/contactly/blob/main/GOOGLE_OAUTH_SETUP.md"
        echo ""
        echo "Quick summary:"
        echo "  1. Create OAuth credentials in Google Cloud Console"
        echo "  2. Run the token generator script locally (requires browser)"
        echo "  3. Set these three values in your environment variables"
        echo "  4. Restart the container"
        echo ""
        exit 1
    else
        echo "INFO: Google OAuth not configured - Google contacts sync will be skipped"
    fi
fi

# Check if iCloud credentials are fully configured.
# Both username and app password must be present for iCloud sync to work.
ICLOUD_CONFIGURED=false
if [ -n "$ICLOUD_USERNAME" ] && [ -n "$ICLOUD_APP_PASSWORD" ]; then
    ICLOUD_CONFIGURED=true
    echo "✓ iCloud credentials configured"
else
    if [ -n "$ICLOUD_USERNAME" ] || [ -n "$ICLOUD_APP_PASSWORD" ]; then
        echo ""
        echo "========================================================================"
        echo "ERROR: Incomplete iCloud configuration!"
        echo "========================================================================"
        echo ""
        echo "Both environment variables are required:"
        echo "  - ICLOUD_USERNAME"
        echo "  - ICLOUD_APP_PASSWORD"
        echo ""
        exit 1
    else
        echo "INFO: iCloud not configured - iCloud contacts sync will be skipped"
    fi
fi

# Validate that at least one contact source (Google or iCloud) is configured.
# The service requires at least one upstream to sync contacts from.
if [ "$GOOGLE_CONFIGURED" = false ] && [ "$ICLOUD_CONFIGURED" = false ]; then
    echo ""
    echo "========================================================================"
    echo "ERROR: No contact sources configured!"
    echo "========================================================================"
    echo ""
    echo "At least one contact source must be configured:"
    echo "  - Google OAuth (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN)"
    echo "  - iCloud (ICLOUD_USERNAME, ICLOUD_APP_PASSWORD)"
    echo ""
    echo "Ideally, configure both sources for complete contact synchronization."
    echo ""
    exit 1
fi

# Validate PBX database credentials are present.
# The PBX database is required as it's the destination for synced contacts.
MISSING_VARS=""

if [ -z "$PBX_DB_HOST" ]; then
    MISSING_VARS="${MISSING_VARS}PBX_DB_HOST "
fi

if [ -z "$PBX_DB_PASSWORD" ]; then
    MISSING_VARS="${MISSING_VARS}PBX_DB_PASSWORD "
fi

if [ -n "$MISSING_VARS" ]; then
    echo ""
    echo "========================================================================"
    echo "ERROR: Missing required PBX database variables!"
    echo "========================================================================"
    echo ""
    echo "Missing variables: $MISSING_VARS"
    echo ""
    echo "Set these variables when running the container:"
    echo ""
    echo "Option 1 - Using docker run with -e flags:"
    echo "  docker run -e PBX_DB_HOST=mysql.example.com -e PBX_DB_PASSWORD=xxxx ..."
    echo ""
    echo "Option 2 - Using docker run with --env-file:"
    echo "  docker run --env-file /path/to/your/.env ghcr.io/aayusharyan/contactly:latest"
    echo ""
    echo "Option 3 - Using docker-compose.yml:"
    echo "  Create a docker-compose.yml with environment variables and run:"
    echo "  docker-compose up -d"
    echo ""
    exit 1
fi

# Display the active configuration for debugging and verification purposes.
# Shows which services are configured and operational parameters.
echo ""
echo "Configuration:"
echo "  Contact Sources:"
echo "    - Google: $([ "$GOOGLE_CONFIGURED" = true ] && echo '✓ Configured' || echo '✗ Not configured')"
echo "    - iCloud: $([ "$ICLOUD_CONFIGURED" = true ] && echo "✓ Configured ($ICLOUD_USERNAME)" || echo '✗ Not configured')"
echo "  PBX MySQL: $PBX_DB_USER@$PBX_DB_HOST:$PBX_DB_PORT/$PBX_DB_NAME"
echo "  Sync Interval: ${SYNC_INTERVAL_HOURS:-6} hours"
echo "  Log Level: ${LOG_LEVEL:-INFO}"
echo ""
echo "========================================================================"
echo "Starting sync scheduler..."
echo "========================================================================"
echo ""

# Replace the shell process with the command passed as arguments.
# This ensures proper signal handling and container lifecycle management.
exec "$@"
