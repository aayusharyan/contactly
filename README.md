# Contactly

**Syncs Google and iCloud contacts with PBX database for caller ID name lookup**

## What It Does

```
Google Contacts + iCloud Contacts
              ↓
      Sync & Merge Service
              ↓
    MySQL pbx_cnam table
              ↓
        Asterisk PBX
              ↓
   Caller ID on Your Phones
```

Syncs contacts from Google and iCloud, merges duplicates intelligently, normalizes phone numbers to E.164 format, and writes them to a MySQL table that your PBX system reads for caller ID lookups.

## Features

- **Incremental Sync**: Only fetches changed contacts using sync tokens and ETags
- **Smart Merging**: Latest-wins collision resolution based on timestamps
- **E.164 Normalization**: Reliable international phone number handling
- **Production Ready**: Docker support, error handling, exponential backoff

## Getting Started

### Prerequisites

- Docker and Docker Compose installed
- MySQL/PBX database (hostname, credentials)
- iCloud app-specific password (see [ICLOUD_AUTH_SETUP.md](ICLOUD_AUTH_SETUP.md))
- Google OAuth credentials (see [GOOGLE_AUTH_SETUP.md](GOOGLE_AUTH_SETUP.md))

### Quick Setup

1. **Pull the Docker image**
   ```bash
   docker pull ghcr.io/aayusharyan/contactly:latest
   ```

2. **Copy the example configuration**
   ```bash
   cp docker-compose.example.yml docker-compose.yml
   ```

3. **Get your credentials**

   - **Google OAuth**: Follow [GOOGLE_AUTH_SETUP.md](GOOGLE_AUTH_SETUP.md) to get your three Google values (Client ID, Client Secret, Refresh Token). Takes ~10 minutes, all browser-based, no coding required.

   - **iCloud**: Follow [ICLOUD_AUTH_SETUP.md](ICLOUD_AUTH_SETUP.md) to generate an app-specific password for iCloud access.

4. **Edit `docker-compose.yml` with your credentials**
   ```bash
   nano docker-compose.yml
   ```

   Fill in:
   - **iCloud**: Email and app-specific password (see [ICLOUD_AUTH_SETUP.md](ICLOUD_AUTH_SETUP.md))
   - **Google OAuth**: Credentials from step 3
   - **MySQL**: Database host, username, password, database name

5. **Start the service**
   ```bash
   docker-compose up -d
   ```

**Done!** The service will sync automatically every 6 hours.

### Verify It's Working

```bash
docker-compose logs -f
```

You should see successful sync messages showing contacts fetched from Google and iCloud.

## Common Commands

```bash
# View logs
docker-compose logs -f

# Check status
docker-compose ps

# Restart
docker-compose restart

# Stop
docker-compose down
```

## Documentation

- **[GOOGLE_AUTH_SETUP.md](GOOGLE_AUTH_SETUP.md)** - Google OAuth setup guide
- **[ICLOUD_AUTH_SETUP.md](ICLOUD_AUTH_SETUP.md)** - iCloud app-specific password guide
- **[docker-compose.example.yml](docker-compose.example.yml)** - Fully annotated configuration reference
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Developer guide (architecture, building from source, contributing)

## Project Structure

```
src/
├── cli/             # Command-line entry points (sync, scheduler)
├── google/          # Google People API integration
├── icloud/          # iCloud CardDAV integration
├── normalize/       # Phone number normalization
├── merge/           # Duplicate contact merging
├── pbx_db/          # MySQL database writer
└── internal_db/     # SQLite sync state storage
```

## Author

**Aayush Sinha** ([@aayusharyan](https://yush.dev))

## License

MIT
