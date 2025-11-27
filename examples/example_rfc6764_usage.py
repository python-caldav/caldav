#!/usr/bin/env python3
"""
Example usage of RFC6764 service discovery in python-caldav

This script demonstrates how the RFC6764 integration works.
"""
from caldav import DAVClient

# Example 1: Automatic RFC6764 discovery with email address
# Username is automatically extracted from the email address
print("Example 1: Using email address (username auto-extracted)")
print("-" * 70)
try:
    client = DAVClient(
        url="user@example.com",  # Domain will be extracted, username preserved
        password="password",  # Username extracted from email, just provide password
    )
    print(f"Client URL after discovery: {client.url}")
    print(f"Username: {client.username}")
except Exception as e:
    print(f"Discovery failed (expected for example.com): {e}")

print("\n")

# Example 2: Automatic RFC6764 discovery with domain
print("Example 2: Using bare domain (RFC6764 discovery enabled by default)")
print("-" * 70)
try:
    client = DAVClient(url="calendar.example.com", username="user", password="password")
    print(f"Client URL after discovery: {client.url}")
except Exception as e:
    print(f"Discovery failed (expected for example.com): {e}")

print("\n")

# Example 3: Disable RFC6764 discovery
print("Example 3: Disable RFC6764 discovery (use feature hints instead)")
print("-" * 70)
try:
    client = DAVClient(
        url="calendar.example.com",
        username="user",
        password="password",
        enable_rfc6764=False,  # Disable discovery, fall back to HTTPS
        features=None,
    )
    print(f"Client URL without discovery: {client.url}")
except Exception as e:
    print(f"Error: {e}")

print("\n")

# Example 4: Full URL bypasses discovery
print("Example 4: Full URL (RFC6764 discovery automatically skipped)")
print("-" * 70)
client = DAVClient(
    url="https://caldav.example.com/dav/", username="user", password="password"
)
print(f"Client URL (no discovery needed): {client.url}")

print("\n")

# Example 5: Using feature hints with NextCloud
print("Example 5: Using feature hints (NextCloud)")
print("-" * 70)
client = DAVClient(
    url="nextcloud.example.com",
    username="user",
    password="password",
    features="nextcloud",
    enable_rfc6764=False,  # Disable discovery to use feature hints
)
print(f"Client URL with NextCloud feature hint: {client.url}")

print("\n")

# Example 6: Direct discovery API usage
print("Example 6: Using discovery API directly")
print("-" * 70)
from caldav.discovery import discover_caldav

try:
    service_info = discover_caldav("user@example.com")
    if service_info:
        print(f"Discovered URL: {service_info.url}")
        print(f"Discovery method: {service_info.source}")
        print(f"Hostname: {service_info.hostname}")
        print(f"Port: {service_info.port}")
        print(f"Path: {service_info.path}")
        print(f"TLS: {service_info.tls}")
    else:
        print("No service discovered")
except Exception as e:
    print(f"Discovery error: {e}")
