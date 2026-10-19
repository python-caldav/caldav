Potentially breaking, on servers that are themselves broken: `save(no_overwrite=True)` now relies on the server honouring `If-None-Match: *`, which every CalDAV server is required to do.  Against a server that ignores it, the save may overwrite an existing object.  The fix is to tell the client that the server is broken: configure it with the server's `features` (e.g. `features: sogo`), or mark `save.if-none-match` unsupported in a hand-written feature list.  Servers known to ignore it: SOGo, Zimbra.

A subclass overriding `_create()` or `_put()` must accept their new keyword argument.
