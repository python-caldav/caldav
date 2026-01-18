HTTP Library Configuration
==========================

The caldav library supports multiple HTTP client libraries. This page explains
the default configuration and how to customize it if needed.

Default Configuration
---------------------

As of v3.0, the caldav library uses **niquests** for both synchronous and
asynchronous HTTP requests. niquests is a modern HTTP library with support
for HTTP/2 and HTTP/3.

httpx is also supported as an alternative for async operations, primarily
for projects that already have httpx as a dependency.

Using httpx for Async
---------------------

If your project already uses httpx and you want caldav to use it too::

    pip install caldav[async]

Or install httpx directly::

    pip install httpx

The async client will automatically use httpx when available, falling back
to niquests otherwise.

Using Alternative Libraries
---------------------------

The caldav library includes fallback support for different HTTP libraries:

**Sync client fallback**: If niquests is not installed, the sync client
(``DAVClient``) will automatically use the ``requests`` library instead.

**Async client fallback**: If httpx is not installed, the async client
(``AsyncDAVClient``) will use niquests with its async support.

Replacing niquests with requests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want to use requests instead of niquests:

1. Install caldav without niquests::

    pip install caldav
    pip uninstall niquests

2. Install requests::

    pip install requests

The sync client will automatically detect that niquests is not available
and use requests instead.

Alternatively, if you're managing dependencies in a project, you can
modify your ``pyproject.toml`` or ``requirements.txt`` to exclude niquests
and include requests.

Using httpx for Sync Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While httpx is primarily used for async operations, you could potentially
use it for sync operations as well. However, this is not the default
configuration and would require code modifications.

HTTP/2 Support
--------------

HTTP/2 support is available with both niquests and httpx. For httpx,
you need to install the optional ``h2`` package::

    pip install h2

The async client will automatically enable HTTP/2 when h2 is available
and the server supports it.

Note: Some servers have compatibility issues with HTTP/2 multiplexing,
particularly when combined with certain authentication methods. The
caldav library includes workarounds for known issues (e.g., with Baikal).
