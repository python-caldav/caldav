#!/usr/bin/env python3
"""
Create a pre-configured Baikal SQLite database for automated testing.

This creates a database with:
- A test user: testuser / testpass
- Digest authentication configured
- Default calendar and addressbook

Usage:
    python create_baikal_db.py
"""

import hashlib
import sqlite3
from pathlib import Path


def create_baikal_db(db_path: Path, username: str = "testuser", password: str = "testpass") -> None:
    """Create a Baikal SQLite database with a test user using official schema."""

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing database if present
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Use the official Baikal SQLite schema
    # This schema is from Baikal's Core/Resources/Db/SQLite/db.sql
    schema_sql = """
CREATE TABLE addressbooks (
    id integer primary key asc NOT NULL,
    principaluri text NOT NULL,
    displayname text,
    uri text NOT NULL,
    description text,
    synctoken integer DEFAULT 1 NOT NULL
);

CREATE TABLE cards (
    id integer primary key asc NOT NULL,
    addressbookid integer NOT NULL,
    carddata blob,
    uri text NOT NULL,
    lastmodified integer,
    etag text,
    size integer
);

CREATE TABLE addressbookchanges (
    id integer primary key asc NOT NULL,
    uri text,
    synctoken integer NOT NULL,
    addressbookid integer NOT NULL,
    operation integer NOT NULL
);

CREATE INDEX addressbookid_synctoken ON addressbookchanges (addressbookid, synctoken);

CREATE TABLE calendarobjects (
    id integer primary key asc NOT NULL,
    calendardata blob NOT NULL,
    uri text NOT NULL,
    calendarid integer NOT NULL,
    lastmodified integer NOT NULL,
    etag text NOT NULL,
    size integer NOT NULL,
    componenttype text,
    firstoccurence integer,
    lastoccurence integer,
    uid text
);

CREATE TABLE calendars (
    id integer primary key asc NOT NULL,
    synctoken integer DEFAULT 1 NOT NULL,
    components text NOT NULL
);

CREATE TABLE calendarinstances (
    id integer primary key asc NOT NULL,
    calendarid integer,
    principaluri text,
    access integer,
    displayname text,
    uri text NOT NULL,
    description text,
    calendarorder integer,
    calendarcolor text,
    timezone text,
    transparent bool,
    share_href text,
    share_displayname text,
    share_invitestatus integer DEFAULT '2',
    UNIQUE (principaluri, uri),
    UNIQUE (calendarid, principaluri),
    UNIQUE (calendarid, share_href)
);

CREATE TABLE calendarchanges (
    id integer primary key asc NOT NULL,
    uri text,
    synctoken integer NOT NULL,
    calendarid integer NOT NULL,
    operation integer NOT NULL
);

CREATE INDEX calendarid_synctoken ON calendarchanges (calendarid, synctoken);

CREATE TABLE calendarsubscriptions (
    id integer primary key asc NOT NULL,
    uri text NOT NULL,
    principaluri text NOT NULL,
    source text NOT NULL,
    displayname text,
    refreshrate text,
    calendarorder integer,
    calendarcolor text,
    striptodos bool,
    stripalarms bool,
    stripattachments bool,
    lastmodified int
);

CREATE TABLE schedulingobjects (
    id integer primary key asc NOT NULL,
    principaluri text NOT NULL,
    calendardata blob,
    uri text NOT NULL,
    lastmodified integer,
    etag text NOT NULL,
    size integer NOT NULL
);

CREATE INDEX principaluri_uri ON calendarsubscriptions (principaluri, uri);

CREATE TABLE locks (
    id integer primary key asc NOT NULL,
    owner text,
    timeout integer,
    created integer,
    token text,
    scope integer,
    depth integer,
    uri text
);

CREATE TABLE principals (
    id INTEGER PRIMARY KEY ASC NOT NULL,
    uri TEXT NOT NULL,
    email TEXT,
    displayname TEXT,
    UNIQUE(uri)
);

CREATE TABLE groupmembers (
    id INTEGER PRIMARY KEY ASC NOT NULL,
    principal_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    UNIQUE(principal_id, member_id)
);

CREATE TABLE propertystorage (
    id integer primary key asc NOT NULL,
    path text NOT NULL,
    name text NOT NULL,
    valuetype integer NOT NULL,
    value string
);

CREATE UNIQUE INDEX path_property ON propertystorage (path, name);

CREATE TABLE users (
    id integer primary key asc NOT NULL,
    username TEXT NOT NULL,
    digesta1 TEXT NOT NULL,
    UNIQUE(username)
);
"""

    # Execute the schema
    cursor.executescript(schema_sql)

    # Create test user with digest auth
    # Digest A1 = MD5(username:BaikalDAV:password)
    realm = "BaikalDAV"
    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()

    cursor.execute("INSERT INTO users (username, digesta1) VALUES (?, ?)", (username, ha1))

    # Create principal for user
    principal_uri = f"principals/{username}"
    cursor.execute(
        "INSERT INTO principals (uri, email, displayname) VALUES (?, ?, ?)",
        (principal_uri, f"{username}@baikal.test", f"Test User ({username})"),
    )

    # Create default calendar
    cursor.execute(
        "INSERT INTO calendars (synctoken, components) VALUES (?, ?)",
        (1, "VEVENT,VTODO,VJOURNAL"),
    )
    calendar_id = cursor.lastrowid

    # Create calendar instance for the user
    cursor.execute(
        """INSERT INTO calendarinstances
           (calendarid, principaluri, access, displayname, uri, calendarorder, calendarcolor)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (calendar_id, principal_uri, 1, "Default Calendar", "default", 0, "#3a87ad"),
    )

    # Create default addressbook for user
    cursor.execute(
        """INSERT INTO addressbooks
           (principaluri, displayname, uri, synctoken)
           VALUES (?, ?, ?, ?)""",
        (principal_uri, "Default Address Book", "default", 1),
    )

    conn.commit()
    conn.close()

    print(f"✓ Created Baikal database at {db_path}")
    print(f"  User: {username}")
    print(f"  Password: {password}")
    print(f"  Realm: {realm}")
    print(f"  Digest A1: {ha1}")


def create_baikal_config(config_path: Path) -> None:
    """Create Baikal config.php file."""

    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Admin password hash (MD5 of 'admin')
    admin_hash = hashlib.md5(b"admin").hexdigest()

    config_content = f"""<?php
##############################################################################
# Baikal Web Server configuration for automated testing
##############################################################################

# This file is auto-generated for testing purposes
# Do not edit manually

##############################################################################
# BAIKAL CONFIGURATION
##############################################################################

# System timezone
define("PROJECT_TIMEZONE", "UTC");

# Encryption key (random for testing)
define("BAIKAL_ENCRYPTION_KEY", "test-encryption-key-for-automated-testing");

# Admin password hash (MD5 of 'admin')
define("BAIKAL_ADMIN_PASSWORDHASH", "{admin_hash}");

# Database configuration
define("PROJECT_DB_MYSQL", FALSE);
define("PROJECT_DB_MYSQL_HOST", "");
define("PROJECT_DB_MYSQL_DBNAME", "");
define("PROJECT_DB_MYSQL_USERNAME", "");
define("PROJECT_DB_MYSQL_PASSWORD", "");

# SQLite database file
define("PROJECT_SQLITE_FILE", "Specific/db/db.sqlite");

# Enable CalDAV
define("BAIKAL_CAL_ENABLED", TRUE);

# Enable CardDAV
define("BAIKAL_CARD_ENABLED", TRUE);

# Invite from address
define("BAIKAL_INVITE_FROM", "noreply@baikal.test");

# Authentication type (Digest)
define("BAIKAL_DAV_AUTH_TYPE", "Digest");

# Configured version
define("BAIKAL_CONFIGURED_VERSION", "0.9.5");

# Admin enabled
define("BAIKAL_ADMIN_ENABLED", TRUE);

# Admin auto-enable
define("BAIKAL_ADMIN_AUTOENABL", TRUE);
"""

    config_path.write_text(config_content)
    print(f"✓ Created Baikal config at {config_path}")


def create_system_config(system_path: Path) -> None:
    """Create Baikal config.system.php file."""

    system_path.parent.mkdir(parents=True, exist_ok=True)

    system_content = """<?php
##############################################################################
# Baikal System configuration
##############################################################################

# Server URL
define("BAIKAL_SERVER_BASEURL", "");

# Server NAME
define("BAIKAL_SERVER_FRIENDLYNAME", "Baikal Test Server");

# Enable password reset
define("BAIKAL_ADMIN_PASSWORDRESET_ENABLE", FALSE);
"""

    system_path.write_text(system_content)
    print(f"✓ Created Baikal system config at {system_path}")


def create_baikal_yaml(yaml_path: Path) -> None:
    """Create Baikal baikal.yaml configuration file for newer Baikal versions."""

    yaml_path.parent.mkdir(parents=True, exist_ok=True)

    # Admin password hash (MD5 of 'admin')
    admin_hash = "21232f297a57a5a743894a0e4a801fc3"

    yaml_content = f"""system:
  configured_version: '0.10.1'
  timezone: 'UTC'
  card_enabled: true
  cal_enabled: true
  invite_from: 'noreply@baikal.test'
  dav_auth_type: 'Digest'
  admin_passwordhash: {admin_hash}
  failed_access_message: 'user %u authentication failure for Baikal'
  auth_realm: BaikalDAV
  base_uri: ''

database:
  encryption_key: 'test-encryption-key-for-automated-testing'
  backend: 'sqlite'
  sqlite_file: '/var/www/baikal/Specific/db/db.sqlite'
  mysql_host: 'localhost'
  mysql_dbname: 'baikal'
  mysql_username: 'baikal'
  mysql_password: 'baikal'
"""

    yaml_path.write_text(yaml_content)
    print(f"✓ Created Baikal YAML config at {yaml_path}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent

    # Create database
    db_path = script_dir / "Specific" / "db" / "db.sqlite"
    create_baikal_db(db_path, username="testuser", password="testpass")

    # Create legacy PHP config files (for older Baikal versions)
    config_path = script_dir / "Specific" / "config.php"
    create_baikal_config(config_path)

    system_path = script_dir / "Specific" / "config.system.php"
    create_system_config(system_path)

    # Create YAML config file (for newer Baikal versions 0.7.0+)
    yaml_path = script_dir / "config" / "baikal.yaml"
    create_baikal_yaml(yaml_path)

    print("\n" + "=" * 70)
    print("Baikal pre-configuration complete!")
    print("=" * 70)
    print("\nYou can now start Baikal with: docker-compose up -d")
    print("\nCredentials:")
    print("  Admin: admin / admin")
    print("  User: testuser / testpass")
    print("  CalDAV URL: http://localhost:8800/dav.php/")
