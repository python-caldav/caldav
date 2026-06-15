HTTP Library Configuration
==========================

As of v3.x, **niquests** is used for HTTP communication. niquests is a backwards-compatible fork of the requests library.  It's a modern HTTP library with support for HTTP/2 and HTTP/3 and many other things.  Due to popular demand, fallbacks to **requests** and **httpx** exists.

Context
-------

There is also information in `GitHub issue #457 <https://github.com/python-caldav/caldav/issues/457>`_

Traditionally the CalDAV library only supported the traditional
**requests** library, but this library seems to be at a dead end,
version 2.0 went into "feature freeze" long ago, but version 3.0 never
materialized (to be fair, the 2.x-series is under active maintenance,
and the 3.0-development hasn't been abandoned - but I'm not holding my
breath).

**Niquests** was dropped to me in a PR.  It is a fork, a drop-in
replacement, and just by replacing the "re" with "ni" in the code I
could close three long-standing issues from the caldav issue tracker.
Niquests (and urllib3-future) started as contributions to the upstream
project, but the changes were rejected.  I've done some research - to
me the technical work done in niquests seems robust, to me niquests
3.x seems to be what requests 3.x should have been.

The change was left in the master branch for quite a while, and pushed
out in the 2.0-release.  Almost immediately after pushing niquests in
2.0, a complaint was raised from a distro package maintainer who found
the niquests-dependency unacceptable.  Due to that the CalDAV library
now has a fallback implemented; it can use requests for sync
communication.

Niquests can do both async and sync communication - the same is true
for **httpx**.  My impression is that httpx used to be the most
popular library candidate for some time - but according to
https://github.com/python-caldav/caldav/issues/611#issuecomment-4278875543
the httpx development seems stagnant, and httpx has even been flagged
as a supply-chain risk in some Reddit-discussions.  httpxyz is a
maintained fork of httpx.  For async communication, the fallback chain
now is niquests, httpxyz and finally httpx if import of the former two
fails.

(I do wonder why it's so difficult to agree on such a simple thing like
"how do we do HTTP requests" in the python environment ...)

Fallbacks
---------

To enable the fallbacks, just ensure the requests and/or httpxyz/httpx library is available and that niquests isn't available.  In virtual environments, fix the dependencies in `pyproject.toml`.

Recommendations
---------------

* If you have strong personal opinions against niquests, then don't use it.  Please share your thoughts at https://github.com/python-caldav/caldav/issues/611
* In general, stick to the package default - niquests.
* In a very sharp production environment, you may consider to use the
  good old requests library, but set an appropriate timeout.  Use the
  sync code.  In general, do not use the async version of CalDAV as it is still a bit
  experimental (as of v3.2.1).
* If you're using the CalDAV library in a sync project that is already
  heavily dependent on the requests library and don't want to drag in
  extra dependencies, go for requests.
* If you're using the CalDAV library in an async project that is
  already heavily dependent on httpx and don't want to drag in extra
  dependencies, use httpx - but do your own due diligence.

Multiplexing
------------

The niquests library supports multiplexing.

A compatibility issue with HTTP/2 multiplexing was found when running nginx with digest auth, so this is disabled by default.  The CalDAV communication may potentially be speeded up a bit by enabling multiplexing.  This is done in the CalDAV server configuration settings, by flagging that the feature `http.multiplexing` is supported.
