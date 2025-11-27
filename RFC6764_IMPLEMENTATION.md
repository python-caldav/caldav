# RFC 6764 Implementation Summary

## Overview

This implementation adds RFC 6764 (Locating Services for Calendaring and Contacts) support to the python-caldav library, enabling automatic CalDAV/CardDAV service discovery from domain names or email addresses.

## What is RFC 6764?

RFC 6764 defines how clients can automatically discover CalDAV and CardDAV services using:
1. **DNS SRV records** - Service location records (_caldavs._tcp, _caldav._tcp)
2. **DNS TXT records** - Optional path information
3. **Well-Known URIs** - Standard endpoints (/.well-known/caldav, /.well-known/carddav)

See: https://datatracker.ietf.org/doc/html/rfc6764

## Changes Made

### 1. New Module: `caldav/discovery.py`

A complete RFC 6764 implementation with:
- `discover_caldav()` - Discover CalDAV services
- `discover_carddav()` - Discover CardDAV services
- `discover_service()` - Generic discovery function
- `ServiceInfo` dataclass - Structured discovery results
- Support for DNS SRV/TXT lookups and well-known URIs
- Automatic TLS preference
- Comprehensive error handling and logging

### 2. Updated: `pyproject.toml`

- Added `dnspython` as a required dependency

### 3. Updated: `caldav/davclient.py`

#### Changes to `_auto_url()`:
- Added RFC 6764 discovery as the first attempt when given a bare domain/email
- Falls back to feature hints if discovery fails
- New parameters: `timeout`, `ssl_verify_cert`, `enable_rfc6764`

#### Changes to `DAVClient.__init__()`:
- Added `enable_rfc6764` parameter (default: `True`)
- Updated to pass discovery parameters to `_auto_url()`
- Enhanced docstring with RFC 6764 examples

#### Changes to `CONNKEYS`:
- Added `"enable_rfc6764"` to connection keys set

## Usage Examples

### Automatic Discovery (Recommended)

```python
from caldav import DAVClient

# Using email address
client = DAVClient(
    url='user@example.com',  # Domain extracted and discovered
    username='user',
    password='password'
)

# Using domain
client = DAVClient(
    url='calendar.example.com',
    username='user',
    password='password'
)
```

### Disable Discovery

```python
# Use feature hints instead of discovery
client = DAVClient(
    url='calendar.example.com',
    username='user',
    password='password',
    enable_rfc6764=False
)
```

### Direct Discovery API

```python
from caldav.discovery import discover_caldav

service_info = discover_caldav('user@example.com')
if service_info:
    print(f"URL: {service_info.url}")
    print(f"Method: {service_info.source}")  # 'srv' or 'well-known'

    client = DAVClient(url=service_info.url, ...)
```

### Full URL (No Discovery)

```python
# Discovery automatically skipped when URL has a path
client = DAVClient(
    url='https://caldav.example.com/dav/',
    username='user',
    password='password'
)
```

## Discovery Process

When `enable_rfc6764=True` and a bare domain/email is provided:

1. **Extract domain** from email address if needed
2. **Try DNS SRV lookup** for `_caldavs._tcp.domain` (TLS preferred)
3. **Try DNS TXT lookup** for path information
4. **If SRV found**: Construct URL from SRV hostname + TXT path
5. **If no SRV**: Try well-known URI (https://domain/.well-known/caldav)
6. **If discovery fails**: Fall back to feature hints or default HTTPS

## Backward Compatibility

✅ **Fully backward compatible**

- Existing code with full URLs: **No change in behavior**
- Existing code with feature hints: **Works as before**
- Discovery only activates for bare domains/emails
- Can be disabled with `enable_rfc6764=False`

## Configuration Options

### Via Constructor
```python
DAVClient(
    url='example.com',
    enable_rfc6764=True,  # Enable/disable discovery
    timeout=10,           # Discovery timeout
    ssl_verify_cert=True  # SSL verification for well-known URI
)
```

### Via Environment Variables
```bash
export CALDAV_URL="user@example.com"
export CALDAV_USERNAME="user"
export CALDAV_PASSWORD="password"
export CALDAV_ENABLE_RFC6764="true"  # Optional
```

### Via Configuration File
```yaml
# ~/.config/caldav/calendar.yaml
caldav_url: user@example.com
caldav_user: user
caldav_pass: password
caldav_enable_rfc6764: true
```

## Logging

The implementation uses the standard Python logging framework:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# You'll see:
# INFO: Discovering caldav service for domain: example.com
# DEBUG: Performing SRV lookup for _caldavs._tcp.example.com
# DEBUG: Found SRV record: caldav.example.com:443 (priority=0, weight=0)
# INFO: RFC6764 discovered service: https://caldav.example.com/dav/ (source: srv)
```

## Testing

See `example_rfc6764_usage.py` for practical examples.

For real-world testing, you'll need:
1. A domain with properly configured DNS SRV/TXT records, OR
2. A server supporting well-known URIs

### Example DNS Configuration

```dns
; SRV record
_caldavs._tcp.example.com. 86400 IN SRV 0 1 443 caldav.example.com.

; TXT record (optional, provides path)
_caldavs._tcp.example.com. 86400 IN TXT "path=/dav/"
```

### Example Web Server Configuration (Nginx)

```nginx
# Well-known URI redirect
location /.well-known/caldav {
    return 301 https://caldav.example.com/dav/;
}
```

## Dependencies

- **dnspython** (new required dependency) - For DNS SRV/TXT lookups
- **niquests** or **requests** (existing) - For well-known URI lookups

## Future Enhancements

Potential improvements:
- [ ] Caching of discovery results (with TTL)
- [ ] Support for weighted random selection of multiple SRV records
- [ ] CardDAV auto-detection alongside CalDAV
- [ ] Integration with `get_davclient()` function
- [ ] Environment variable `CALDAV_DISABLE_RFC6764` for global control
- [ ] Metrics/telemetry for discovery success rates

## Security Considerations

1. **DNS Security**: Discovery relies on DNS, which can be spoofed. For production use, consider DNSSEC.
2. **TLS Verification**: The implementation verifies SSL certificates by default.
3. **Timeout**: Discovery has a 10-second default timeout to prevent hanging.
4. **Fallback**: Failed discovery falls back to feature hints or defaults.

## References

- [RFC 6764 - Locating Services for Calendaring](https://datatracker.ietf.org/doc/html/rfc6764)
- [RFC 5785 - Well-Known URIs](https://datatracker.ietf.org/doc/html/rfc5785)
- [RFC 6125 - Certificate Verification](https://datatracker.ietf.org/doc/html/rfc6125)
- [RFC 4791 - CalDAV](https://datatracker.ietf.org/doc/html/rfc4791)
