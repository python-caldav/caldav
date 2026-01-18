HTTP Library Configuration
==========================

The caldav library supports multiple HTTP client libraries. This page explains
the default configuration and how to customize it if needed.

As of v3.0, the caldav library uses **niquests** for both synchronous and
asynchronous HTTP requests. niquests is a modern HTTP library with support
for HTTP/2 and HTTP/3.

The library also supports requests (for sync communication) and httpx
(for async communication).  If you for some reason or another don't
want to drag in the niquests dependency, then you may simply edit the
pyproject.toml file and replace niquests with requests and httpx.

HTTP/2 Support
--------------

HTTP/2 support is available with both niquests and httpx. For httpx,
you need to install the optional ``h2`` package::

    pip install h2

The async client will automatically enable HTTP/2 when h2 is available
and the server supports it.

Note: Some servers have compatibility issues with HTTP/2 multiplexing,
particularly when combined with digest authentication methods and
nginx server.  (TODO: update the doc on this - I will most likely
remove the "do multiplexing by default"-logic before releasing v3.0)
