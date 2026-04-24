# caldav

This project is a CalDAV ([RFC4791](https://datatracker.ietf.org/doc/html/rfc4791)) client library for Python.

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
    calendars = principal.get_calendars()
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
        calendars = await principal.get_calendars()
        for cal in calendars:
            print(f"Calendar: {cal.name}")

asyncio.run(main())
```

## Documentation and other links

The user documentation (up-to-date with version 3.2) is embedded under `docs/source` - a rendered copy is available at https://caldav.readthedocs.io/

Other documentation:

* [This file](README.md)
* [Changelog](CHANGELOG.md)
* [Contributors guide](CONTRIBUTING.md)
* [Contact information](CONTACT.md)
* [Code of Conduct](CODE_OF_CONDUCT)
* [Security Policy](SECURITY.md)
* [AI policy and AI disclaimer](AI-POLICY.md)
* [Apache License](COPYING.APACHE)
* [GPL license](COPYING.GPL)

There is also a directory [docs/design](docs/design) containing lots of documents, mostly AI-generated, containing things like design decisions and other things that neither is deemed important enough to have a document on the root of the project nor deemed to be "user documentation".

The package is published at [Pypi](https://pypi.org/project/caldav)

## HTTP Libraries

The sync client uses [niquests](https://github.com/jawah/niquests) by default (with fallback to [requests](https://requests.readthedocs.io/)). The async client uses [httpx](https://www.python-httpx.org/) if installed, otherwise falls back to niquests. See [HTTP Library Configuration](docs/source/http-libraries.rst) for details.

## Licences

The caldav library is dual-licensed under the [GNU GENERAL PUBLIC LICENSE Version 3](COPYING.GPL) or the [Apache License 2.0](COPYING.APACHE).
