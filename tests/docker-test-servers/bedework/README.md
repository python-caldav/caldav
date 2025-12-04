# Bedework CalDAV Server Test Configuration

## Overview

Bedework is an enterprise calendar system built on JBoss. The Docker image used for testing is `ioggstream/bedework:latest`.

## Default Configuration

The Bedework Docker image comes pre-configured and requires no additional setup files:

- **Default User**: `vbede`
- **Default Password**: `bedework`
- **CalDAV Endpoint**: `http://localhost:8804/ucaldav/user/vbede/`
- **Web Interface**: `http://localhost:8804/bedework/`

## Startup

Bedework runs on JBoss and takes longer to start than other test servers (60-120 seconds).

## Calendars

The default user comes with two calendars:
- `calendar` - Main calendar for events
- `polls` - Bedework-specific polling calendar

## No Configuration Files Needed

Unlike other test servers (SOGo, Baikal), Bedework doesn't require pre-seeded configuration files. The Docker image is ready to use as-is.
