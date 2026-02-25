# Apple CalendarServer (CCS) Test Server

Apple's CalendarServer (ccs-calendarserver) running in Docker for the caldav
library test suite.

## Overview

- **Image**: `pluies/ccs-calendarserver:latest` (Debian Jessie, Python 2)
- **Port**: 8807 (mapped to container's 8008)
- **Users**: user01/user01, user02/user02, admin/admin
- **Storage**: File-based (SQLite), ephemeral (tmpfs)

Note: Apple CalendarServer is archived/orphaned since 2019. This Docker image
is based on Debian Jessie and Python 2. It's included for historical
compatibility testing.

## Quick Start

```bash
./start.sh
```

## Stop

```bash
./stop.sh
```

## Configuration

- `conf/caldavd.plist` - Main server config (HTTP on port 8008, no SSL)
- `conf/auth/accounts.xml` - User accounts (XML-based directory service)
- `conf/auth/augments.xml` - Calendar/addressbook enablement
- `conf/auth/resources.xml` - Resources (empty)
- `conf/auth/proxies.xml` - Proxy delegates (empty)

## Architecture

CCS uses UID-based principal URLs:
- Principal: `/principals/__uids__/{GUID}/`
- Calendar home: `/calendars/__uids__/{GUID}/`

The server auto-initializes its data directory on first start. No setup script
is needed — users are defined in `accounts.xml`.
