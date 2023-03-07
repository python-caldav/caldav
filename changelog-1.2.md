## What's Changed from 1.1 to 1.2

Bugfixing is the most important thing in the 1.2.x-series.  Again, touching the authentication code (this time the bearer authentication support introduced in 1.0) caused breakages for some people, despite lots of functional tests.

**Full Changelog**: https://github.com/python-caldav/caldav/compare/v1.1.3...v1.2.0

### Cleaned out some python2-specific stuff

Pull request by @danigm in https://github.com/python-caldav/caldav/pull/228

Python2 has not been tested for quite some time, hence it has probably been broken since one of the 0.x-releases.  I decided to officially drop support for python2 in version 1.0 - but since the release was overdue I procrastinated merging this pull request.  To avoid breaking changes in v1.x, I threw in an assert instead.

### New feature - custom http headers

Pull request by @JasonSanDiego in https://github.com/python-caldav/caldav/pull/288 (with style fixup in https://github.com/python-caldav/caldav/pull/291 ) allows `headers` parameter to the `DAVClient` constructor.

Rationale given in https://github.com/python-caldav/caldav/issues/285 :

> I'm using Nextcloud and want to retrieve calendar (read only) subscriptions along with the normal read/write calendars. Nextcloud supports two ways of doing this. The easier of the two is to pass the custom HTTP header: X-NC-CalDAV-Webcal-Caching: On

### Bugfix - basic auth broken for some servers

A bug was introduced in version 1.0, via https://github.com/python-caldav/caldav/pull/260 - the code would only work if there was a space in the `WWW-Authenticate` header.  This works for most servers as they will challenge for credentials using a header like `WWW-Authenticate: Basic realm="My CalDAV server"` - however, `WWW-Authenticate: Basic` is fully allowed by RFC2617.

Thanks to @jdrozdnovak for debugging and reporting.

https://github.com/python-caldav/caldav/issues/289 - https://github.com/python-caldav/caldav/pull/290

### Bugfix - invalid password caused infinite recursion

Thanks to @bvanjeelharia for reporting (actually the traceback was reported already by @robinmayol in https://github.com/python-caldav/caldav/issues/270 but we failed to connect the dots).

https://github.com/python-caldav/caldav/issues/295 - https://github.com/python-caldav/caldav/pull/296
