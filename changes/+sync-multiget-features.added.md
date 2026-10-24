Compatibility features for behaviours a sync client depends on, as found by calendaring-sync (https://github.com/PyCalendar/calendaring-sync/blob/c40782bc7afe7b350fe63bf27ef13374c280ea8b/docs/reference/server-compatibility.rst), each with a probe in caldav-server-tester:

- `delete.missing` and `delete.missing.if-match`: a DELETE of a missing object answers 404, and one with If-Match answers as the plain one does (Baikal, Davis, Nextcloud, CCS, OX, Robur, Purelymail and Infomaniak answer 412 with it).
- `save.etag.matches-stored`: a strong ETag in a PUT answer belongs to what was stored (Radicale, Xandikos, SOGo, CCS, Zimbra, Bedework 5 and Infomaniak rewrite the object and still answer with one).
- `sync-token.initial-sync`, `sync-token.delete.created-and-deleted` and `sync-token.recreated`: which members a sync-collection report lists.
- `multiget`, `multiget.missing-href` and `multiget.limit`, and `propfind.limit`: a calendar-multiget answers a missing href with a 404, and a multiget or a Depth: 1 PROPFIND answers every href (Stalwart stops at its maxResults, with a 507).

The Stalwart test container now runs with a maxResults of 50 (`STALWART_MAX_RESULTS`), so the limit can be probed with few objects.
