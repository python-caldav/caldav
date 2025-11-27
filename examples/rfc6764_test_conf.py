#!/usr/bin/env python3
"""
This script will run through all domains found in:
 * conf_private.py
 * compatibility_hints
... and check if they support the RFC.
"""
from sys import path

path.insert(0, "..")
path.insert(0, ".")


try:
    from tests.conf_private import caldav_servers
except:
    caldav_servers = []
from caldav.discovery import discover_caldav
from caldav.lib.url import URL
from caldav import compatibility_hints

urls = []
domains = []
for server in caldav_servers:
    url = server.get("url")
    urls.append(url)

for compconf in dir(compatibility_hints):
    if compconf.startswith("_"):
        continue
    compconf = getattr(compatibility_hints, compconf)
    if hasattr(compconf, "get"):
        urls.append(compconf.get("auto-connect.url", {}).get("domain"))

for url in urls:
    if not url:
        continue
    if "//" in url:
        url = URL(url)
        url = url.unauth().netloc.split(":")[0]
    hostsplit = url.split(".")
    ## This asserts there is at least one dot in the domain,
    ## and that no TLDs have those srv records.
    for i in range(2, len(hostsplit) + 1):
        domains.append(".".join(hostsplit[-i:]))

discovered_urls = []

for domain in domains:
    print("-" * 70)
    service_info = discover_caldav(domain)
    if service_info:
        print(f"Domain: {domain}")
        print(f"Discovered URL: {service_info.url}")
        print(f"Discovery method: {service_info.source}")
        print(f"Hostname: {service_info.hostname}")
        print(f"Port: {service_info.port}")
        print(f"Path: {service_info.path}")
        print(f"TLS: {service_info.tls}")
        if service_info.url:
            discovered_urls.append(service_info.url)
    else:
        print(f"No service discovered for {domain}")

assert discovered_urls
