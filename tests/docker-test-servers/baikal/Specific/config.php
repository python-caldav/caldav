<?php
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
define("BAIKAL_ADMIN_PASSWORDHASH", "21232f297a57a5a743894a0e4a801fc3");

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
