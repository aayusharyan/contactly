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

# Verify that all three Google OAuth credentials are provided together.
# If only some are set, display an error with instructions.
# If none are set, log an informational message that Google sync will be skipped.
if [ -n "$GOOGLE_CLIENT_ID" ] && [ -n "$GOOGLE_CLIENT_SECRET" ] && [ -n "$GOOGLE_REFRESH_TOKEN" ]; then
    echo "✓ Google OAuth credentials configured via environment variables"
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
        echo "The service will continue running but Google sync will fail."
        echo "========================================================================"
        echo ""
    else
        echo "INFO: Google OAuth not configured - Google contacts sync will be skipped"
    fi
fi

# Build a list of missing required environment variables for iCloud and PBX.
# Exit with error if any required variables are missing.
MISSING_VARS=""

if [ -z "$ICLOUD_USERNAME" ]; then
    MISSING_VARS="${MISSING_VARS}ICLOUD_USERNAME "
fi

if [ -z "$ICLOUD_APP_PASSWORD" ]; then
    MISSING_VARS="${MISSING_VARS}ICLOUD_APP_PASSWORD "
fi

if [ -z "$PBX_DB_HOST" ]; then
    MISSING_VARS="${MISSING_VARS}PBX_DB_HOST "
fi

if [ -z "$PBX_DB_PASSWORD" ]; then
    MISSING_VARS="${MISSING_VARS}PBX_DB_PASSWORD "
fi

if [ -n "$MISSING_VARS" ]; then
    echo "ERROR: Missing required environment variables: $MISSING_VARS"
    echo ""
    echo "Set these variables when running the container:"
    echo ""
    echo "Option 1 - Using docker run with -e flags:"
    echo "  docker run -e ICLOUD_USERNAME=your@icloud.com -e ICLOUD_APP_PASSWORD=xxxx ..."
    echo ""
    echo "Option 2 - Using docker run with --env-file:"
    echo "  docker run --env-file /path/to/your/.env contactly:latest"
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
echo "  iCloud User: $ICLOUD_USERNAME"
echo "  PBX MySQL: $PBX_DB_USER@$PBX_DB_HOST:$PBX_DB_PORT/$PBX_DB_NAME"
echo "  Sync Interval: ${SYNC_INTERVAL_HOURS:-6} hours"
echo "  Log Level: ${LOG_LEVEL:-INFO}"
echo "  Google OAuth: $([ -n "$GOOGLE_REFRESH_TOKEN" ] && echo '✓ Configured' || echo '✗ Not configured')"
echo ""
echo "========================================================================"
echo "Starting sync scheduler..."
echo "========================================================================"
echo ""

# Replace the shell process with the command passed as arguments.
# This ensures proper signal handling and container lifecycle management.
exec "$@"
