HTTP Library Configuration
==========================

As of v3.x, **niquests** is the preferred, recommended and supported library for HTTP communication. niquests is a backwards-compatible fork of the requests library.  It's a modern HTTP library with support for HTTP/2 and HTTP/3 and many other things.

Due to popular demand, fallbacks to **requests** and to the **httpx** family (httpx, httpxyz, httpx2) exist.

v4.x is planned to come without explicit dependencies on any HTTP library - the logic is that the consumer probably already imports some HTTP-library, and probably does not want to drag in another dependency.  For backward compatibility, it will be necessary to depend on ``caldav[niquests]`` rather than just ``caldav``.  Going forward from 3.3.0, every odd patch release will have ``niquests`` included in the dependencies, while every even patch release will have no http library dependencies, allowing consumers that don't want to drag in ``niquests`` (and the related ``urllib3-future``) to avoid them without having to patch the ``pyproject.toml`` file.

Context
-------

Somehow it seems extraordinarily difficult to agree on something as
simple as "how do we do HTTP requests" in the python environment ...

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
popular library candidate for some time - but there was some `drama
about it
<https://github.com/python-caldav/caldav/issues/611#issuecomment-4278875543>`_.
The package **httpx2** seems to be the continuation of the httpx
project.

The fallback chain for async communication now is niquests, httpx2,
httpxyz and finally httpx, whichever imports first.

The three httpx variants share one API, and the CalDAV library treats
them interchangeably.  One difference is worth knowing if you write code
around this: httpxyz registers itself in ``sys.modules`` under the name
``httpx``, so ``import httpx`` gets you httpxyz; httpx2 does not, and
stays ``import httpx2``.

Sync communication falls back to requests, not to httpx as of v3.3.0 - there is an issue on using httpx also for sync communication, see https://github.com/python-caldav/caldav/issues/696

More information in the issue tracker:

* `GitHub issue #457 <https://github.com/python-caldav/caldav/issues/457>`_
* `GitHub issue #611 <https://github.com/python-caldav/caldav/issues/611>`_
* `GitHub issue #690 <https://github.com/python-caldav/caldav/issues/690>`_

Fallbacks
---------

To enable the fallbacks, just ensure the requests and/or httpxyz/httpx2/httpx library is available and that niquests isn't available.  In virtual environments, pin things to the latest even release.

Recommendations
---------------

* If you're using some other http-library, are happy with it and don't want to overthink things, then there is no need to do anything at all - except, if your project depends on httpx you should probably do some due diligence and consider httpx2.
* If you have strong personal opinions against niquests, then you do have the option of actively avoiding it.  Please share your thoughts at https://github.com/python-caldav/caldav/issues/611
* In a very sharp production environment, you may consider to use the good old requests library, but set an appropriate timeout.  In a very sharp production environment (as of 3.x), use the CalDAV library in a sync way, the async version of CalDAV still lacks some real-world testing.
* Otherwise, stick to the package default - niquests.  Starting from 4.0, you will need to depend on ``caldav[niquests]`` rather than just ``caldav``.

Multiplexing
------------

The niquests library supports multiplexing.

A compatibility issue with HTTP/2 multiplexing was found when running nginx with digest auth, so this is disabled by default.  The CalDAV communication may potentially be speeded up a bit by enabling multiplexing.  This is done in the CalDAV server configuration settings, by flagging that the feature `http.multiplexing` is supported.
