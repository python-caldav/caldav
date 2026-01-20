# Analysis: get_davclient() vs DAVClient() Direct Instantiation

## Current State

### What is get_davclient()?

`get_davclient()` is a **factory function** that creates a `DAVClient` instance with configuration from multiple sources (davclient.py:1225-1311):

```python
def get_davclient(
    check_config_file: bool = True,
    config_file: str = None,
    config_section: str = None,
    testconfig: bool = False,
    environment: bool = True,
    name: str = None,
    **config_data,
) -> DAVClient:
```

### Configuration Sources (in priority order):

1. **Direct parameters**: `get_davclient(url="...", username="...", password="...")`
2. **Environment variables**: `CALDAV_URL`, `CALDAV_USERNAME`, `CALDAV_PASSWORD`, etc.
3. **Test configuration**: `./tests/conf.py` or `./conf.py` (for development/testing)
4. **Config file**: INI-style config file (path from `CALDAV_CONFIG_FILE` or parameter)

### Current Usage Patterns

**Documentation (docs/source/tutorial.rst)**:
- ALL examples use `get_davclient()` ✓
- **Recommended pattern**: `from caldav import get_davclient`

```python
from caldav import get_davclient

with get_davclient() as client:
    principal = client.principal()
    calendars = principal.get_calendars()
```

**Examples (examples/*.py)**:
- ALL examples use `DAVClient()` directly ✗
- Pattern: `from caldav import DAVClient`

**Tests (tests/*.py)**:
- Mostly use `DAVClient()` directly for mocking and unit tests
- Pattern: Direct instantiation for test control

**Actual Code Comment (davclient.py:602)**:
```python
## Deprecation TODO: give a warning, user should use get_davclient or auto_calendar instead.  Probably.
```

There's already a TODO suggesting `DAVClient()` direct usage should be discouraged!

## Advantages of get_davclient()

### 1. **12-Factor App Compliance** ✓
Supports configuration via environment variables (config stored in env, not code):

```bash
export CALDAV_URL=https://caldav.example.com
export CALDAV_USERNAME=alice
export CALDAV_PASSWORD=hunter2
python my_script.py  # No hardcoded credentials!
```

```python
# In code:
with get_davclient() as client:  # Automatically reads env vars!
    ...
```

### 2. **Testing Flexibility** ✓
Can use test servers without code changes:

```bash
export PYTHON_CALDAV_USE_TEST_SERVER=1
python my_script.py  # Uses test server from conf.py
```

### 3. **Configuration File Support** ✓
Supports INI-style config files:

```ini
# ~/.caldav.conf
[default]
caldav_url = https://caldav.example.com
caldav_user = alice
caldav_pass = hunter2
```

```python
with get_davclient() as client:  # Reads ~/.caldav.conf automatically
    ...
```

### 4. **Consistency** ✓
All official documentation uses it - this is the "blessed" way.

### 5. **Future-Proofing** ✓
- Can add discovery, retry logic, connection pooling, etc. without breaking user code
- Can add more config sources (keyring, cloud secrets, etc.)

## Disadvantages of get_davclient()

### 1. **Hidden Magic** ✗
Config source priority isn't obvious:
```python
get_davclient(url="A")  # Uses "A"
# But if CALDAV_URL=B is set, which wins? (Answer: parameter, but not obvious)
```

### 2. **Harder to Understand** ✗
More indirection - need to understand config file format, env var names, etc.

### 3. **Less Explicit** ✗
Pythonic code prefers "explicit is better than implicit":
```python
# Explicit (clear what's happening):
client = DAVClient(url="...", username="...", password="...")

# Implicit (where does config come from?):
client = get_davclient()
```

### 4. **Not in __init__.py** ✗
Currently not exported:
```python
# Doesn't work:
from caldav import get_davclient  # ImportError!

# Must use:
from caldav import get_davclient
```

## Usage Statistics

**Documentation**: 100% use `get_davclient()` ✓
**Examples**: 0% use `get_davclient()` (all use `DAVClient` directly) ✗
**Tests**: ~5% use `get_davclient()` (mostly direct instantiation)
**Real-world**: Unknown (but docs recommend `get_davclient`)

**Interpretation**: There's a disconnect between what's documented (factory) and what's demonstrated (direct).

## Recommendations

### Option A: Make get_davclient() Primary (Your Suggestion) ✓✓✓

**Advantages:**
- Aligns with existing documentation
- Better for production use (env vars, config files)
- Future-proof (can add features without breaking API)
- Follows factory pattern (like urllib3, requests, etc.)

**Implementation:**
1. Export from `__init__.py`:
   ```python
   from .davclient import get_davclient
   __all__ = ["get_davclient", "DAVClient"]  # Export both
   ```

2. Update all examples to use `get_davclient()`:
   ```python
   from caldav import get_davclient

   with get_davclient(url="...", username="...", password="...") as client:
       ...
   ```

3. Add deprecation warning to `DAVClient.__init__()` (optional):
   ```python
   def __init__(self, ...):
       warnings.warn(
           "Direct DAVClient() instantiation is deprecated. "
           "Use caldav.get_davclient() instead.",
           DeprecationWarning,
           stacklevel=2
       )
   ```

4. Keep `DAVClient` public for:
   - Testing (mocking)
   - Advanced use cases
   - Type hints: `client: DAVClient`

### Option B: Make Both Equal

Keep both as first-class citizens:
- `DAVClient()` for simple/explicit use
- `get_davclient()` for config-based use

Update docs to show both patterns.

### Option C: Direct Only

Deprecate `get_davclient()`, use only `DAVClient()`.

**Problems:**
- Loses env var support
- Loses config file support
- Goes against current documentation
- Less future-proof

## Async Implications

For async API, we should be consistent:

```python
# If we prefer factories:
from caldav import aio

async with aio.get_client(url="...", username="...", password="...") as client:
    ...

# Or direct (current aio.py approach):
from caldav import aio

async with aio.CalDAVClient(url="...", username="...", password="...") as client:
    ...
```

## Verdict: Option A (Factory Primary) ✓

**YES, using `get_davclient()` as primary is a good idea** because:

1. ✅ Already documented as recommended approach
2. ✅ Supports production use cases (env vars, config files)
3. ✅ Future-proof (can add connection pooling, retries, etc.)
4. ✅ Follows TODO comment in code (line 602)
5. ✅ Consistent with 12-factor app principles

**Action Items:**

1. Export `get_davclient` from `caldav.__init__`
2. Update all examples to use factory
3. Create async equivalent: `aio.get_client()` or `aio.get_davclient()`
4. Consider soft deprecation of direct `DAVClient()` (warning, not error)
5. Keep `DAVClient` class public for testing and type hints

**Proposed Async API:**

```python
# caldav/aio.py
async def get_client(
    url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    *,
    check_config_file: bool = True,
    config_file: Optional[str] = None,
    environment: bool = True,
    **config_data,
) -> CalDAVClient:
    """
    Get an async CalDAV client with configuration from multiple sources.

    Configuration priority:
    1. Direct parameters
    2. Environment variables (CALDAV_*)
    3. Config file

    Example:
        # From parameters:
        async with await aio.get_client(url="...", username="...") as client:
            ...

        # From environment:
        async with await aio.get_client() as client:  # Uses CALDAV_* env vars
            ...
    """
    # Read config from env, file, etc. (like sync get_davclient)
    # Return CalDAVClient(**merged_config)
```

Usage:
```python
from caldav import aio

# Simple:
async with await aio.get_client(url="...", username="...", password="...") as client:
    calendars = await client.get_calendars()

# From environment:
async with await aio.get_client() as client:  # Reads CALDAV_* env vars
    calendars = await client.get_calendars()
```

## Alternative Naming

Since we're designing the async API from scratch, we could use cleaner names:

```python
# Option 1: Parallel naming
caldav.get_davclient()      # Sync
caldav.aio.get_davclient()  # Async (or get_client)

# Option 2: Simpler naming
caldav.get_client()     # Sync
caldav.aio.get_client() # Async

# Option 3: connect() - REJECTED
caldav.connect()     # Sync
caldav.aio.connect() # Async
```

**Option 3 rejected**: `connect()` implies immediate connection attempt, but `DAVClient.__init__()` doesn't connect to the server. It only stores configuration. Actual network I/O happens on first method call.

**Recommendation**: Stick with **Option 1** (`get_davclient`) for consistency.

## Adding Connection Probe

### The Problem

Current behavior:
```python
# This succeeds even if server is unreachable:
client = get_davclient(url="https://invalid-server.com", username="x", password="y")

# Error only happens on first actual call:
principal = client.principal()  # <-- ConnectionError here
```

Users don't know if credentials/URL are correct until first use.

### Proposal: Optional Connection Probe

Add a `probe` parameter to verify connectivity:

```python
def get_davclient(
    check_config_file: bool = True,
    config_file: str = None,
    config_section: str = None,
    testconfig: bool = False,
    environment: bool = True,
    name: str = None,
    probe: bool = True,  # NEW: verify connection
    **config_data,
) -> DAVClient:
    """
    Get a DAVClient with optional connection verification.

    Args:
        probe: If True, performs a simple OPTIONS request to verify
               the server is reachable and responds. Default: True.
               Set to False to skip verification (useful for testing).
    """
    client = DAVClient(**merged_config)

    if probe:
        try:
            # Simple probe - just check if server responds
            client.options(str(client.url))
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to CalDAV server at {client.url}: {e}"
            ) from e

    return client
```

### Usage

```python
# Verify connection immediately:
with get_davclient(url="...", username="...", password="...") as client:
    # If we get here, server is reachable
    principal = client.principal()

# Skip probe (for testing or when server might be down):
with get_davclient(url="...", probe=False) as client:
    # No connection attempt yet
    ...
```

### Async Version

```python
async def get_davclient(
    ...,
    probe: bool = True,
    **config_data,
) -> AsyncDAVClient:
    """Async version with connection probe"""
    client = AsyncDAVClient(**merged_config)

    if probe:
        try:
            await client.options(str(client.url))
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to CalDAV server at {client.url}: {e}"
            ) from e

    return client

# Usage:
async with await get_davclient(url="...") as client:
    # Connection verified
    ...
```

### Benefits

1. **Fail fast** - errors caught immediately, not on first use
2. **Better UX** - clear error message about connectivity
3. **Opt-out available** - `probe=False` for testing or when needed
4. **Minimal overhead** - single OPTIONS request
5. **Validates config** - catches typos in URL, wrong credentials, etc.

### Considerations

**What should the probe do?**

Option A (minimal): Just `OPTIONS` request
- ✅ Fast
- ✅ Doesn't require authentication (usually)
- ❌ Doesn't verify credentials

Option B (thorough): Try to get principal
- ✅ Verifies credentials
- ✅ Verifies CalDAV support
- ❌ Slower
- ❌ Requires valid credentials

**Recommendation**: Start with **Option A** (OPTIONS), consider Option B later or as separate parameter:

```python
get_davclient(
    ...,
    probe: bool = True,           # OPTIONS request
    verify_auth: bool = False,    # Also try to authenticate
)
```

### Default Value

**Should probe default to True or False?**

Arguments for `True`:
- ✅ Better UX - catches errors early
- ✅ Fail fast principle
- ✅ Most production use cases want this

Arguments for `False`:
- ✅ Backward compatible (no behavior change)
- ✅ Faster (no extra request)
- ✅ Works when server is temporarily down

**Recommendation**: Default to `True` for new async API, `False` for sync (backward compat).

```python
# Sync (backward compatible):
def get_davclient(..., probe: bool = False) -> DAVClient:
    ...

# Async (new, opinionated):
async def get_davclient(..., probe: bool = True) -> AsyncDAVClient:
    ...
```
