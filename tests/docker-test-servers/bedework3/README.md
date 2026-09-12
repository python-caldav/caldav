# Bedework 3.10.3 CalDAV Server Test Configuration

## Overview

Bedework is an enterprise calendar system built on JBoss. This directory runs
the `ioggstream/bedework:latest` Docker image.

**That image is ancient.** It is a `quickstart-3.10.3` tree on openjdk-8, built
2018-11-05, and it cannot be rebuilt - the quickstart zip its Dockerfile fetches
from `dev.bedework.org` is gone. The compatibility profile in
`caldav/compatibility_hints.py` is therefore named `bedework_3_10_3`: it says
nothing about what a current Bedework does.

For a current Bedework, see `../bedework/`, which builds an image from the
upstream galleon feature pack.

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
