Potentially breaking, on servers that are themselves broken: `save(no_overwrite=True)` and `save(no_create=True)` now rely on the server honouring `If-None-Match: *` and `If-Match: *`, which every CalDAV server is required to do.  Against a server that does not, an existing object may be overwritten, a missing one created, or a legitimate update refused.  The fix is to tell the client that the server is broken: configure it with the server's `features` (e.g. `features: sogo`), or mark `save.if-none-match` and `save-load.mutable.if-match-wildcard` correctly in a hand-written feature list.  Servers known not to honour them, as of this release:

- `If-None-Match: *`: SOGo, Zimbra
- `If-Match: *`: Bedework, GMX, iCloud, Posteo, Radicale, SOGo, Yahoo, Zimbra

A subclass overriding `_create()` or `_put()` must accept their new `wildcard=` keyword.
