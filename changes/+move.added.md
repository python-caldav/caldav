`compatibility_hints`: new features `move`, `move.overwrite` (with `move.overwrite.existing` and `move.overwrite.free-name`) and `move.if-match`, for WebDAV MOVE of an object into another calendar (RFC 4918 section 9.9).  caldav has no `move()` yet (https://github.com/python-caldav/caldav/issues/841); the hints are there for it.

- SOGo and Zimbra ignore both `Overwrite: F` onto an existing object and an outdated If-Match, Radicale and Xandikos the If-Match.
- GMX refuses `Overwrite: F` onto an existing object with 405 (`ungraceful`).
- Robur does not support MOVE (501).
- Bedework (3.10 and 5) ignores the If-Match too, and refuses `Overwrite: F` with 412 even onto a free name (`move.overwrite.free-name` is `broken`), so a client can send the header only where the name is known to be taken.
