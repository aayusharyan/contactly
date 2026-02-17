# Contactly - Contributing Guide

**Technical documentation for developers building from source or contributing**

## Quick Start

### Prerequisites

- Python 3.9+
- pip, Git
- MySQL database for testing

### Setup

```bash
# Clone and install
git clone <repo-url>
cd contacts
pip install -r requirements.txt

# Configure .env file
cp .env.example .env
# Edit .env with your credentials

# Run sync
python -m src.cli.sync
```

## Architecture Overview

### System Flow

```
Google Contacts + iCloud Contacts
              ↓
      Sync & Normalize
              ↓
    SQLite (local state)
              ↓
      Merge & Dedupe
              ↓
    MySQL pbx_cnam table
              ↓
   Asterisk/PBX reads it
```

### Component Structure

```
src/
├── cli/             # sync.py (manual), scheduler.py (6h interval)
├── google/          # Google People API + OAuth
├── icloud/          # CardDAV + ETag tracking
├── normalize/       # E.164 phone formatting
├── merge/           # Latest-wins collision resolution
├── pbx_db/          # MySQL writer
└── internal_db/     # SQLite state storage
```

## Core Components

### 1. Google Integration (`src/google/`)

**client.py:**
- OAuth 2.0 with automatic token refresh
- People API connections.list
- Sync cursors for incremental updates (7-day expiry)
- Handles pagination

**sync.py:**
- Stores sync cursor in database
- Falls back to full sync on expiry
- Tracks added/updated/deleted via metadata.deleted flag

**Incremental Sync:**
- First sync: Fetches all, gets nextSyncToken
- Subsequent: Only changed contacts (90-99% reduction)
- Cursor expires after 7 days → auto fallback to full sync

### 2. iCloud Integration (`src/icloud/`)

**client.py:**
- CardDAV protocol over HTTPS
- App-specific password auth
- PROPFIND to discover addressbook
- ETags for change detection
- Rate limiting: 0.5s delay per 10 requests

**sync.py:**
- Compares stored ETags with server
- Only fetches modified vCards (95-99% reduction)
- vCard parsing via vobject library
- Deleted = href missing from PROPFIND

### 3. Normalization (`src/normalize/`)

**PhoneNormalizer:**
- Converts to E.164: +[country][number]
- Uses phonenumbers library (libphonenumber)
- Examples: +14155552671 (US), +442071234567 (UK)

**ContactNormalizer:**
- Standardizes structure
- Extracts best display name
- Validates emails
- Creates (phone, name) tuples for PBX

### 4. Merge Logic (`src/merge/`)

**Collision Resolution:**
1. Group contacts by E.164 phone number
2. Compare source_updated_at timestamps
3. Latest wins (if equal: Google > iCloud)
4. Create/update canonical_contact
5. Store all sources for audit trail

**Example:**
```python
# Google: John Smith, updated 2026-02-15
# iCloud: John A. Smith, updated 2026-02-16
# Winner: iCloud (newer) → "John A. Smith"
```

### 5. Publishing (`src/pbx_db/`)

**MySQL Table:**
```sql
CREATE TABLE pbx_cnam (
  e164 VARCHAR(20) PRIMARY KEY,
  display_name VARCHAR(500),
  updated_at DATETIME,
  source VARCHAR(50)
);
```

Operations: INSERT new, UPDATE changed, DELETE removed

### 6. Storage (`src/internal_db/`)

**SQLite Schema:**
- `source_contact`: Per-source data + etag
- `canonical_contact`: Merged contacts
- `sync_state`: Cursors + timestamps

## Development

### Run Options

```bash
# Manual sync
python -m src.cli.sync

# Scheduled (6h interval)
python -m src.cli.scheduler

# Build Docker image
docker-compose -f docker/docker-compose.yml up -d
```

### Test Individual Components

```python
# Google sync
from src.google import GoogleContactsClient, GoogleContactsSync
from src.internal_db import get_session

client = GoogleContactsClient('credentials.json', 'token.json')
with get_session() as session:
    sync = GoogleContactsSync(client, session)
    print(sync.sync())

# iCloud sync
from src.icloud import ICloudCardDAVClient, ICloudContactsSync

client = ICloudCardDAVClient('email@icloud.com', 'app-password')
with get_session() as session:
    sync = ICloudContactsSync(client, session)
    print(sync.sync())

# Merge
from src.normalize import ContactNormalizer
from src.merge import ContactMerger

with get_session() as session:
    merger = ContactMerger(session, ContactNormalizer())
    print(merger.merge_all())

# Publish to PBX
from src.pbx_db import init_pbx_db, sync_to_pbx, verify_pbx_sync

pbx_url = "mysql+pymysql://user:pass@host:3306/asterisk"
init_pbx_db(pbx_url)
with get_session() as session:
    print(sync_to_pbx(session, pbx_url))
    print(verify_pbx_sync(session, pbx_url))
```

### Monitoring

```bash
# Check sync state
sqlite3 contacts_sync.db "SELECT * FROM sync_state;"

# View contacts
sqlite3 contacts_sync.db "SELECT best_e164, best_display_name FROM canonical_contact LIMIT 10;"

# Check PBX table
mysql -u asterisk -p asterisk -e "SELECT * FROM pbx_cnam LIMIT 10;"
```

## Rate Limiting

### Google People API

**Quotas (free tier):**
- 300 requests/minute
- ~20,000 requests/day

**Our usage:**
- Full sync: ~10 requests (1000 contacts)
- Incremental: ~1 request
- 6h interval: ~4 syncs/day = ~4 requests/day
- **< 0.1% of quota**

**429 Handling:**
- Exponential backoff: 60s, 120s, 240s, 480s, 960s
- Max 5 retries

### iCloud CardDAV

**Observed limits:**
- ~10 req/sec sustained = throttling
- ~100 req/min burst = 503 errors

**Our strategy:**
- 6h polling
- 0.5s delay per 10 requests
- ETag filtering reduces by 95%+
- Typical: 1 PROPFIND + <5 GETs

**503 Handling:**
- Same exponential backoff as Google
- Jitter to prevent thundering herd

## Performance

### Database Sizes (1000 contacts)

- SQLite: ~1.5 MB (source_contact + canonical_contact)
- MySQL: ~100 KB (pbx_cnam)

### Sync Times

**Full Sync (1000 contacts):**
- Google: 10-15s
- iCloud: 30-60s (throttled)
- Merge: 5-10s
- Publish: 2-5s
- **Total: 50-90s**

**Incremental (10 changes):**
- Total: 8-16s

### PBX Query Performance

```sql
SELECT display_name FROM pbx_cnam WHERE e164='+14155551234' LIMIT 1;
```
- Indexed on PRIMARY KEY
- **< 1ms query time**

## Asterisk Integration

### ODBC Configuration

**`/etc/odbc.ini`:**
```ini
[asterisk-connector]
Driver = MySQL
Server = localhost
Database = asterisk
User = asterisk
Password = your_password
```

**`/etc/asterisk/func_odbc.conf`:**
```ini
[CNAM_LOOKUP]
dsn=asterisk-connector
readsql=SELECT display_name FROM pbx_cnam WHERE e164='${ARG1}' LIMIT 1
```

**`/etc/asterisk/extensions.conf`:**
```ini
[from-trunk]
exten => _X.,1,Set(CALLERID(name)=${ODBC_CNAM_LOOKUP(${CALLERID(num)})})
same => n,Dial(SIP/100)
```

## Deployment Patterns

### Systemd Service

```ini
[Unit]
Description=contactly
After=network.target mysql.service

[Service]
Type=simple
ExecStart=/path/to/venv/bin/python -m src.cli.scheduler
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

### Kubernetes CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: contacts-sync
spec:
  schedule: "0 */6 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: sync
            image: ghcr.io/aayusharyan/contactly:latest
            command: ["python", "-m", "src.cli.sync"]
            envFrom:
            - secretRef:
                name: contacts-sync-secrets
          restartPolicy: OnFailure
```

## Troubleshooting

### Google: Sync Token Expired
- Normal after 7 days
- Auto falls back to full sync

### Google: 429 Rate Limit
- Wait and retry
- Check for multiple processes
- 6h interval should stay under quota

### iCloud: 503 Throttling
- Increase delay between requests
- Check for concurrent syncs
- Increase interval to 12h

### PBX Count Mismatch
- Re-run: `sync_to_pbx()` and `verify_pbx_sync()`
- Check MySQL connection

### Phone Numbers Not Normalizing
- Set correct region: `ContactNormalizer(default_region='GB')`
- Check DEBUG logs for failures

## Security

**Developers:**
- Never commit credentials.json, token.json, .env
- Use app-specific passwords for iCloud
- chmod 600 sensitive files
- Rotate passwords quarterly

**Production:**
- Use Docker secrets or env variables
- TLS for MySQL connections
- Dedicated MySQL user (limited to pbx_cnam table)
- Google: contacts.readonly scope only

## Performance Tuning

```bash
# Adjust sync interval
SYNC_INTERVAL_HOURS=12

# Set phone region
DEFAULT_PHONE_REGION=GB
```

## Key Takeaways

- **Incremental sync** reduces API calls by 90-99%
- **Latest-wins** collision resolution (simple, deterministic)
- **E.164 normalization** ensures unique phone IDs
- **Exponential backoff** handles rate limits gracefully
- **SQLite for state**, MySQL for PBX reads
- **Production-ready**: Error handling, retry logic, stays within free tiers

The code is well-commented - read the source for implementation details.
