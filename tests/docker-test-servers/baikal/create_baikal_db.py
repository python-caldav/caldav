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
import os
import sqlite3
from pathlib import Path


def create_baikal_db(db_path: Path, username: str = "testuser", password: str = "testpass") -> None:
    """Create a Baikal SQLite database with a test user."""

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing database if present
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            digesta1 TEXT
        )
    """)

    # Create principals table
    cursor.execute("""
        CREATE TABLE principals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uri TEXT UNIQUE,
            email TEXT,
            displayname TEXT
        )
    """)

    # Create calendars table
    cursor.execute("""
        CREATE TABLE calendars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            principaluri TEXT,
            displayname TEXT,
            uri TEXT,
            description TEXT,
            components TEXT,
            ctag INTEGER,
            calendarcolor TEXT,
            timezone TEXT,
            calendarorder INTEGER,
            UNIQUE(principaluri, uri)
        )
    """)

    # Create calendarobjects table
    cursor.execute("""
        CREATE TABLE calendarobjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            calendardata BLOB,
            uri TEXT,
            calendarid INTEGER,
            lastmodified INTEGER,
            etag TEXT,
            size INTEGER,
            componenttype TEXT,
            firstoccurence INTEGER,
            lastoccurence INTEGER,
            uid TEXT,
            UNIQUE(calendarid, uri)
        )
    """)

    # Create addressbooks table
    cursor.execute("""
        CREATE TABLE addressbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            principaluri TEXT,
            displayname TEXT,
            uri TEXT,
            description TEXT,
            ctag INTEGER,
            UNIQUE(principaluri, uri)
        )
    """)

    # Create cards table
    cursor.execute("""
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            carddata BLOB,
            uri TEXT,
            addressbookid INTEGER,
            lastmodified INTEGER,
            etag TEXT,
            size INTEGER,
            UNIQUE(addressbookid, uri)
        )
    """)

    # Create addressbookchanges table
    cursor.execute("""
        CREATE TABLE addressbookchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uri TEXT,
            synctoken INTEGER,
            addressbookid INTEGER,
            operation INTEGER
        )
    """)

    # Create calendarchanges table
    cursor.execute("""
        CREATE TABLE calendarchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uri TEXT,
            synctoken INTEGER,
            calendarid INTEGER,
            operation INTEGER
        )
    """)

    # Create test user with digest auth
    # Digest A1 = MD5(username:BaikalDAV:password)
    realm = "BaikalDAV"
    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()

    cursor.execute(
        "INSERT INTO users (username, digesta1) VALUES (?, ?)",
        (username, ha1)
    )

    # Create principal for user
    principal_uri = f"principals/{username}"
    cursor.execute(
        "INSERT INTO principals (uri, email, displayname) VALUES (?, ?, ?)",
        (principal_uri, f"{username}@baikal.test", f"Test User ({username})")
    )

    # Create default calendar for user
    cursor.execute(
        """INSERT INTO calendars
           (principaluri, displayname, uri, components, ctag, calendarcolor, calendarorder)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (principal_uri, "Default Calendar", "default", "VEVENT,VTODO,VJOURNAL", 1, "#3a87ad", 0)
    )

    # Create default addressbook for user
    cursor.execute(
        """INSERT INTO addressbooks
           (principaluri, displayname, uri, ctag)
           VALUES (?, ?, ?, ?)""",
        (principal_uri, "Default Address Book", "default", 1)
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


if __name__ == "__main__":
    script_dir = Path(__file__).parent

    # Create database
    db_path = script_dir / "Specific" / "db" / "db.sqlite"
    create_baikal_db(db_path, username="testuser", password="testpass")

    # Create config files
    config_path = script_dir / "Specific" / "config.php"
    create_baikal_config(config_path)

    system_path = script_dir / "Specific" / "config.system.php"
    create_system_config(system_path)

    print("\n" + "="*70)
    print("Baikal pre-configuration complete!")
    print("="*70)
    print("\nYou can now start Baikal with: docker-compose up -d")
    print("\nCredentials:")
    print("  Admin: admin / admin")
    print("  User: testuser / testpass")
    print("  CalDAV URL: http://localhost:8800/dav.php/")
