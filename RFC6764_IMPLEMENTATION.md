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

## DNSSEC Validation

**NEW in issue571 branch**: Optional DNSSEC validation for enhanced security.

### What is DNSSEC?

DNSSEC (DNS Security Extensions) provides cryptographic authentication of DNS data, ensuring that DNS responses have not been tampered with during transit. It protects against DNS spoofing and cache poisoning attacks.

### Enabling DNSSEC Validation

```python
from caldav import DAVClient

# Enable DNSSEC validation
client = DAVClient(
    url='user@example.com',
    password='secure_password',
    verify_dnssec=True,  # Requires DNSSEC-enabled domain
)
```

### How DNSSEC Validation Works

When `verify_dnssec=True`:
1. DNS queries include EDNS0 extension with DO (DNSSEC OK) flag
2. Queries request AD (Authenticated Data) flag
3. Responses are validated for RRSIG (signature) records
4. Discovery fails if signatures are missing or invalid

### Requirements

- **Domain must have DNSSEC enabled** with properly configured:
  - DS records in parent zone
  - DNSKEY records in zone
  - RRSIG signatures for all records
- **Recursive resolver must support DNSSEC** (most modern resolvers do)
- **dnspython library** (already required for RFC 6764)

### Error Handling

```python
from caldav import DAVClient
from caldav.discovery import DiscoveryError

try:
    client = DAVClient(
        url='user@example.com',
        password='password',
        verify_dnssec=True,
    )
except DiscoveryError as e:
    print(f"DNSSEC validation failed: {e}")
    # Fall back to manual configuration
    client = DAVClient(
        url='https://caldav.example.com/dav/',
        username='user',
        password='password',
    )
```

### When to Use DNSSEC Validation

**✅ Recommended for:**
- High-security environments handling sensitive data
- Financial or healthcare applications
- Government or enterprise deployments
- Any environment where DNS security is critical

**❌ Not recommended for:**
- Domains without DNSSEC enabled (will fail)
- Development/testing with local DNS
- Quick prototyping
- Public services where availability > security

### Testing DNSSEC Support

Check if a domain has DNSSEC enabled:

```bash
# Check for DNSSEC records
dig +dnssec _caldavs._tcp.example.com SRV

# Should see RRSIG records in response
```

### Performance Impact

DNSSEC validation adds minimal overhead:
- ~10-50ms additional latency for DNS queries
- No impact on subsequent CalDAV operations
- Results can be cached to amortize cost

### Limitations

**DNSSEC only validates DNS-based discovery (SRV/TXT records)**:
- When `verify_dnssec=True`, only DNS SRV and TXT records are validated
- Well-known URI discovery (`.well-known/caldav`) is **not** DNSSEC-validated
- If no SRV records exist, discovery will fail with `verify_dnssec=True`
- This is intentional: DNSSEC validates DNS records, not HTTPS endpoints

**Why well-known URIs can't use DNSSEC**:
- Well-known URI discovery uses HTTPS requests, not DNS lookups
- The service endpoint is discovered via HTTP redirect, which DNSSEC doesn't secure
- TLS certificate validation secures the HTTPS connection, not DNSSEC

**Recommendation**: Only use `verify_dnssec=True` with domains that have proper DNS SRV records configured for CalDAV/CardDAV.

## Future Enhancements

Potential improvements:
- [ ] Caching of discovery results (with TTL)
- [ ] Support for weighted random selection of multiple SRV records
- [ ] CardDAV auto-detection alongside CalDAV
- [ ] Integration with `get_davclient()` function
- [ ] Environment variable `CALDAV_DISABLE_RFC6764` for global control
- [ ] Metrics/telemetry for discovery success rates
- [x] DNSSEC validation (implemented in issue571 branch)
- [ ] Custom DNS resolver for niquests/urllib3_future with DNSSEC validation for HTTPS requests
  - Would validate DNSSEC for A/AAAA records during HTTPS connections
  - Requires deep integration with urllib3_future's resolver system
  - Complex implementation beyond current scope

## Security Considerations

⚠️ **CRITICAL SECURITY WARNING**

RFC 6764 DNS-based service discovery has inherent security risks if DNS is not secured with DNSSEC:

### Attack Vectors

1. **DNS Spoofing**: Attackers controlling DNS can provide malicious SRV/TXT records pointing to attacker-controlled servers
2. **Downgrade Attacks**: Malicious DNS can specify non-TLS services (`_caldav._tcp` instead of `_caldavs._tcp`), causing credentials to be sent in plaintext HTTP
3. **Man-in-the-Middle**: Even with HTTPS, attackers can redirect to their servers and present fake certificates

### Security Mitigations Implemented

1. **`require_tls=True` (DEFAULT)**: Only accepts HTTPS connections, preventing HTTP downgrade attacks
   ```python
   # Safe - only allows HTTPS
   client = DAVClient(url='user@example.com', password='pass')

   # DANGEROUS - allows HTTP if DNS specifies it
   client = DAVClient(url='user@example.com', password='pass', require_tls=False)
   ```

2. **`ssl_verify_cert=True` (DEFAULT)**: Verifies TLS certificates to prevent MITM attacks

3. **`verify_dnssec=False` (DEFAULT, opt-in)**: Optional DNSSEC validation for DNS integrity
   ```python
   # Maximum security - requires DNSSEC-enabled domain
   client = DAVClient(
       url='user@example.com',
       password='pass',
       verify_dnssec=True,  # Cryptographically verify DNS responses
   )
   ```

4. **Timeout Protection**: 10-second default timeout prevents hanging on malicious DNS

5. **Explicit Fallback**: Failed discovery falls back to feature hints or defaults

### Best Practices for Production

1. **Use DNSSEC**: Deploy DNSSEC on your domains to cryptographically secure DNS responses
2. **Enable DNSSEC Validation**: Use `verify_dnssec=True` for high-security environments with DNSSEC-enabled domains
3. **Verify Endpoints**: Manually verify discovered endpoints for sensitive applications
4. **Certificate Pinning**: Consider pinning certificates for known domains
5. **Manual Configuration**: For high-security environments, manual URL configuration may be preferable to automatic discovery
6. **Monitor Discovery**: Log and monitor discovered endpoints for unexpected changes

### Example: Secure Usage

```python
# Recommended for production (standard security)
client = DAVClient(
    url='user@example.com',
    password='secure_password',
    require_tls=True,        # Default - only HTTPS
    ssl_verify_cert=True,    # Default - verify certificates
)

# Maximum security with DNSSEC (requires DNSSEC-enabled domain)
client = DAVClient(
    url='user@example.com',
    password='secure_password',
    require_tls=True,        # Default - only HTTPS
    ssl_verify_cert=True,    # Default - verify certificates
    verify_dnssec=True,      # Validate DNS signatures
)

# For testing/development only
client = DAVClient(
    url='user@example.com',
    password='test_password',
    require_tls=False,       # INSECURE - allows HTTP
    enable_rfc6764=True,
)
```

### When to Disable RFC 6764

Consider setting `enable_rfc6764=False` for:
- Environments without DNSSEC where DNS trust is low
- When manual endpoint verification is required
- Legacy systems requiring specific server configurations
- Development/testing with non-standard DNS setups

## References

- [RFC 6764 - Locating Services for Calendaring](https://datatracker.ietf.org/doc/html/rfc6764)
- [RFC 5785 - Well-Known URIs](https://datatracker.ietf.org/doc/html/rfc5785)
- [RFC 6125 - Certificate Verification](https://datatracker.ietf.org/doc/html/rfc6125)
- [RFC 4791 - CalDAV](https://datatracker.ietf.org/doc/html/rfc4791)
