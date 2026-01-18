# caldav

This project is a CalDAV ([RFC4791](http://www.ietf.org/rfc/rfc4791.txt)) client library for Python.

Features:

 * create, modify calendar
 * create, update and delete event
 * search events by dates
 * async support via `caldav.aio` module
 * etc.

## Quick Start

```python
from caldav import get_davclient

with get_davclient() as client:
    principal = client.principal()
    calendars = principal.calendars()
    for cal in calendars:
        print(f"Calendar: {cal.name}")
```

## Async API

For async/await support, use the `caldav.aio` module:

```python
import asyncio
from caldav import aio

async def main():
    async with aio.get_async_davclient() as client:
        principal = await client.principal()
        calendars = await principal.calendars()
        for cal in calendars:
            print(f"Calendar: {cal.name}")

asyncio.run(main())
```

The documentation was updated as of version 2.0, and is available at https://caldav.readthedocs.io/

The package is published at [Pypi](https://pypi.org/project/caldav)

Licences:

Caldav is dual-licensed under the [GNU GENERAL PUBLIC LICENSE Version 3](COPYING.GPL) or the [Apache License 2.0](COPYING.APACHE).
