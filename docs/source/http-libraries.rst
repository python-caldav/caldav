HTTP Library Configuration
==========================

As of v3.x, **niquests** is used for HTTP communication. niquests is a backwards-compatible fork of the requests library.  It's a modern HTTP library with support for HTTP/2 and HTTP/3 and many other things.  Due to popular demand, fallbacks to **requests** and **httpx** exists.

Context
-------

There is also information in `GitHub issue #457 <https://github.com/python-caldav/caldav/issues/457>`_

Traditionally the CalDAV library only supported the traditional
**requests** library, but this library seems to be at a dead end,
version 2.0 went into "feature freeze" long ago, but version 3.0 never
materialized.  It was suggested to replace it with **niquests**.  Niquests (and urllib3-future) started as contributions to the upstream project, but the changes were rejected.  Some research has been done before accepting niquests as a dependency in the CalDAV library.

Niquests is a fork, a drop-in replacement, and just replacing the "re"
with "ni" in the code solved three long-standing issues.  The change
was left in the master branch for quite a while, and pushed out in the
2.0-release.  Almost immediately after pushing niquests in 2.0,
a complaint was raised from a distro package maintainer who found
niquests unacceptable.  Due to that the CalDAV library now has a
fallback implemented; it can use requests for sync communication.

For async communications (and also as a replacement for requests in
sync usage), **httpx** seems to have been the most popular library
candidate.  However, niquests supports async communication.  It was
decided to support both niquests and httpx for async communication.

According to
https://github.com/python-caldav/caldav/issues/611#issuecomment-4278875543
the httpx development seems stagnant, and httpx is even flagged as a
supply-chain risk in some Reddit-discussions.  It seems like the http
user space is filled with drama and intrigues.

Fallbacks
---------

To enable the fallbacks, just ensure the requests and/or httpx library is available and that niquests isn't available.  In virtual environments, fix the dependencies in `pyproject.toml`.

Recommendations
---------------

* In general, stick to the package default - niquests.
* In a very sharp production environment, you may consider to use the
  good old requests library, but set an appropriate timeout.  Use the
  sync code, do not use async as the async support is still a bit
  experimental.
* If you're using the CalDAV library in a sync project that is already
  heavily dependent on the requests library and don't want to drag in
  extra dependencies, go for requests.
* If you're using the CalDAV library in an async project that is
  already heavily dependent on httpx and don't want to drag in extra
  dependencies, use httpx - but do your own due diligence.
* If you have strong personal opinions against niquests, then don't use it.  Please share your thoughts at https://github.com/python-caldav/caldav/issues/611

Multiplexing
------------

The niquests library supports multiplexing.

A compatibility issue with HTTP/2 multiplexing was found when running nginx with digest auth, so this is disabled by default.  The CalDAV communication may potentially be speeded up a bit by enabling multiplexing.  This is done in the CalDAV server configuration settings, by flagging that the feature `http.multiplexing` is supported.
