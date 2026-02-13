HTTP Library Configuration
==========================

As of v3.x, **niquests** is used for HTTP communication. niquests is a backwards-compatible fork of the requests library.  It's a modern HTTP library with support for HTTP/2 and HTTP/3 and many other things.  However, it's a bit controversial, so I've decided to support some fallbacks.

Historical context
------------------

There is also information in `GitHub issue #457 <https://github.com/python-caldav/caldav/issues/457>`_

I got in a pull request suggesting to replace the "good old" requests
libary with **niquests**.  While development of the requests library is
more or less stagnant, niquests supports HTTP/2.0, HTTP/3.0, async
operations and a lot more.  I held back releasing this change until
v2.0.  Short time after v2.0 was released, I got a complaint from a
package maintainer - he found the niquests dependency to be
unacceptable.

The niquests and urllib3-future packages seems to have started as
patches to the requests and urllib3 libraries, but was never accepted
by the maintainers.  It may have been due to a "not invented
here"-syndrome, it may have been due to disagreements on design
decisions, it may have been due to personal conflicts - or, perhaps
the quality of the code was found not to be good enough.  It works for
me.  I've had Claude to do a code review of niquests and urllib3 - it
gave a thumbs-up for Niquests, while urllib3.future could benefit from
some refactoring (claude also recommends shedding backward
compatibility).

I see some possible reasons why one would like to avoid niquests:
  * Many projects are already dependent on requests and/or httpx, and one
may not want to drag in another HTTP-dependency.
  * Some may argue that requests and httpx are safer options because
the code have had more eyeballs (This *is* true, but if everybody
thought "nobody ever got fired for choosing IBM/Microsoft", we'd
probably still be stuck with MS/Dos on floppy disks!).
  * Ref `GitHub issue #530 <https://github.com/python-caldav/caldav/issues/530>`_ there is a concern is that the urllib3-future fork is messy (though, the urllib3 author denies this).

Fallbacks implemented
---------------------

I respect that people may have concerns, hence I've implemtened fallback logic:

* **Sync client**: Falls back to `requests` if niquests is not installed
* **Async client**: Uses `httpx` if installed, otherwise uses niquests

This means all that is needed for getting the library to work without
dragging in the niquest dependency is to change the dependencies in
the `pyproject.toml` file.

If this is not possible for you for one reason or another (like, the project depends on pulling packages from pypi), please ask me gently (i.e. in `#530 <https://github.com/python-caldav/caldav/issues/530>`_) to release a patch-level version where niquests is an optional dependency.

HTTP/2 Support
--------------

While niquests supports HTTP/2 and HTTP/3 out of the box, the HTTP/2-support in httpx is considered a bit experimental and disabled by default.  HTTP/2 will be enabled with httpx, if the optional ``h2`` package is installed.

Multiplexing problems
---------------------

Some servers (particularly the combination nginx with digest auth) does have compatibility issues with HTTP/2 multiplexing, so this is disabled by default.  The CalDAV communication may potentially be speeded up a bit by enabling multiplexing.  This is done in the CalDAV server configuration settings, by flagging that the featue `http.multiplexing` is supported.
