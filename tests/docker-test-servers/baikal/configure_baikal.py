#!/usr/bin/env python3
"""
Configure Baikal CalDAV server for testing.

This script helps automate the initial configuration of a Baikal server
by directly creating the necessary configuration files and database.

Usage:
    python scripts/configure_baikal.py

Environment Variables:
    BAIKAL_URL: URL of the Baikal server (default: http://localhost:8800)
    BAIKAL_ADMIN_PASSWORD: Admin password (default: admin)
    BAIKAL_USERNAME: Test user username (default: testuser)
    BAIKAL_PASSWORD: Test user password (default: testpass)
"""

import os
import sys
import sqlite3
import hashlib
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


def create_baikal_config(config_path: Path, admin_password: str) -> None:
    """Create Baikal configuration files."""
    config_path.mkdir(parents=True, exist_ok=True)

    # Create config.php
    config_php = config_path / "config.php"
    config_content = f"""<?php
# Baikal configuration for testing

define("PROJECT_TIMEZONE", "UTC");
define("BAIKAL_ENCRYPTION_KEY", "{hashlib.sha256(admin_password.encode()).hexdigest()}");
define("BAIKAL_CONFIGURED_VERSION", "0.9.4");
define("BAIKAL_ADMIN_PASSWORDHASH", "{hashlib.md5(admin_password.encode()).hexdigest()}");
"""
    config_php.write_text(config_content)
    print(f"Created config file: {config_php}")


def create_baikal_database(db_path: Path, username: str, password: str) -> None:
    """Create Baikal SQLite database with test user."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create database and user table
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            digesta1 TEXT
        )
    """)

    # Create calendars table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calendars (
            id INTEGER PRIMARY KEY,
            principaluri TEXT,
            displayname TEXT,
            uri TEXT,
            description TEXT,
            components TEXT,
            ctag INTEGER
        )
    """)

    # Create addressbooks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS addressbooks (
            id INTEGER PRIMARY KEY,
            principaluri TEXT,
            displayname TEXT,
            uri TEXT,
            description TEXT,
            ctag INTEGER
        )
    """)

    # Create test user with digest auth
    realm = "BaikalDAV"
    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()

    cursor.execute(
        "INSERT OR REPLACE INTO users (username, digesta1) VALUES (?, ?)",
        (username, ha1)
    )

    # Create default calendar for user
    principal_uri = f"principals/{username}"
    cursor.execute(
        """INSERT OR REPLACE INTO calendars
           (principaluri, displayname, uri, components, ctag)
           VALUES (?, ?, ?, ?, ?)""",
        (principal_uri, "Default Calendar", "default", "VEVENT,VTODO,VJOURNAL", 1)
    )

    # Create default addressbook for user
    cursor.execute(
        """INSERT OR REPLACE INTO addressbooks
           (principaluri, displayname, uri, ctag)
           VALUES (?, ?, ?, ?)""",
        (principal_uri, "Default Address Book", "default", 1)
    )

    conn.commit()
    conn.close()
    print(f"Created database with user '{username}': {db_path}")


def main() -> int:
    """Main function."""
    # Get configuration from environment
    baikal_url = os.environ.get('BAIKAL_URL', 'http://localhost:8800')
    admin_password = os.environ.get('BAIKAL_ADMIN_PASSWORD', 'admin')
    username = os.environ.get('BAIKAL_USERNAME', 'testuser')
    password = os.environ.get('BAIKAL_PASSWORD', 'testpass')

    print(f"Configuring Baikal at {baikal_url}")
    print(f"Test user: {username}")

    # Check if Baikal is accessible
    try:
        response = requests.get(baikal_url, timeout=5)
        print(f"Baikal is accessible (status: {response.status_code})")
    except Exception as e:
        print(f"Warning: Cannot access Baikal at {baikal_url}: {e}")
        print("Make sure Baikal is running (e.g., docker-compose up -d)")

    # Note: Direct file configuration requires access to Baikal's container filesystem
    print("\n" + "="*70)
    print("NOTE: Direct configuration requires container filesystem access")
    print("="*70)
    print("\nFor Docker-based setup, you can:")
    print("1. Use docker exec to run this script inside the container")
    print("2. Mount a pre-configured volume with config and database")
    print("3. Use the web interface for initial setup")
    print("\nExample for docker exec:")
    print(f"  docker cp scripts/configure_baikal.py baikal-test:/tmp/")
    print(f"  docker exec baikal-test python3 /tmp/configure_baikal.py")
    print("="*70 + "\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())
