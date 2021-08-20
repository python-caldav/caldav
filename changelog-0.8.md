# Changelog v0.8 -> v0.8.1

## Documentation

## Various bugfixes

Commits: ca12e15fadfd49dffcf01119e1b227f568fadf70, 5196ee7d64eae6c70d3cd602d40b55525400380e, 7b81cbc54237e2c1c33072329bc2359d0ef61e5f, 87510930a89fe9f8098346b356b4412ce35610f5, 4db75faf67b7355c89ada1119865b6dfc1d783c4 17ce149635c0a4d44015d60a2d5362dec28d521c

Github issues: https://github.com/python-caldav/caldav/issues/146, https://github.com/python-caldav/caldav/issues/148 https://github.com/python-caldav/caldav/issues/150

Credits: Paul Waite, @brainsky, @TabError

# Changelog v0.7.1 -> v0.8

This is a replacement of the old ChangeLog file, admittedly in a non-standard format.  I believe it's more essential to group the changes by purpose than by date/file modified, and I think it's important to have references to the issues in the issue tracker and commit IDs.  Author is changed to "credits", emails are left out (though it's probably moot since those are publically available in the git repository anyway), and I'm skipping crediting myself.

## Support for WebDAV sync-tokens

Github issues: https://github.com/python-caldav/caldav/issues/87, https://github.com/python-caldav/caldav/issues/122 https://github.com/python-caldav/caldav/issues/122

Commits: 35a49ae860df1e8e7c6cec554d34ff6bc4a0c2dd, 11768b9b5aee24278b2a60209d3550933720374d, cec96c51bf2a770bd041e8db3896425f3ab997cd, bc138c55a7e85e4411cc4614f5f7da6f7ae97a36, d5c17b522bef2e62038528f609fe320e91720f87, c838a30f4c5aa343ec27c78571907e6963732403, bc589093a34f0ed0ef489ad5e9cba048750c9837

Credits: Nylas

## Improved support for iCloud, Google

Apple seems to have more or less abandoned their position in the CalDAV ecosystem.  While they've never said officially that iCloud supports CalDAV, they do support some basic CalDAV operations.  There hasn't been done much dedicated work on supporting iCloud in this release, but a lot of testing has been done, some few tweaks, and some documentation.

Google has two APIs, one legacy API and one new API.  The new API is not supported yet.  As with iCloud, while very little dedicated work has been done to support Google, I've done a lot of testing, some few tweaks, and some documentation.  Unlike Apple, Google is very transparent on their (lack of proper) CalDAV support.

Github issues: https://github.com/python-caldav/caldav/issues/3, https://github.com/python-caldav/caldav/issues/119

Commits: d50c2d2db8cec19911ae1857032dca16ada18c58, e129185e74d9d600113aaad0997e09e564dcfd89, c3d4d405240392c07d84f2e432bd696ccc6901f0, f4733ea37b4f1251d24b48cbc20022f4b11c5ab9

Credits: Nylas

## Work on support for RFC6635, scheduling/RVSP (partially done)

Convenience-methods for finding CalDAV inbox and outbox, for accepting calendar invites, for adding invitations to an icalendar object, doing freebusy-requests towards email addresses and misc.  Should be ready for use, but it's relatively untested.

Commits: 1e8ee44e9b11051fdba7414a325956338f543a6b, 2238d093aea6c04b0cdb2c877c6fde45ef0118a7, 0f4cdb8bec113212b4901e367a79542c35572991, 32722bf3b8337a4839396f21406f441199a6b02c, 

Github issues: https://github.com/python-caldav/caldav/issues/125

Credits: Nylas

## Multiget (partially done)

Method for doing a multiget for fetching multiple events in one http
request has been added, but more work is needed (multiget should be
utilized by the library when applicable without the end-user having to
be explicit on it, it's missing test code).

Github issues: https://github.com/python-caldav/caldav/issues/115, https://github.com/python-caldav/caldav/pull/111

Commits: ed89a5911e1e9ba38302fef5febc5f03906f84bd

Credits: Mincheol Song (@mtorange)

## Documentation improvements

Github issues: https://github.com/python-caldav/caldav/issues/120, https://github.com/tobixen/calendar-cli/issues/82, https://github.com/python-caldav/caldav/pull/135, https://github.com/python-caldav/caldav/pull/108, https://github.com/python-caldav/caldav/issues/107

Commits: ce2e2b701cf80718679800de647df285d401a4c8, bc138c55a7e85e4411cc4614f5f7da6f7ae97a36, 048d6be742178d238956172837ca01a57252ddc4, 48a790cd0fce42855e240c39f219b111511b6dcd, 2dfcdeca570877d33297bacf40fc805c32f75708, 8940ecaf405eb5f955e9ebf032775edc16b9ce19, 3ca4eaf99e4e83253e60356ef408c2bdf3703628

Credits: @olf42, @tfinke, Teymour Aldridge (@teymour-aldridge), @VanKurt

## Improved calendar API

* Possible to look up a calendar by name
* Possible to access a calendar by url from the DAVClient object
* New method calendar.get_supported_components()

Github issues: https://github.com/python-caldav/caldav/issues/101 https://github.com/python-caldav/caldav/pull/17, https://github.com/python-caldav/caldav/issues/114, https://github.com/python-caldav/caldav/issues/134, https://github.com/python-caldav/caldav/issues/124

Commits: 37769cfa21670e9c547f2bf877baee835de39cc7, 3754d13270a5326a595c7ad290ebdf003f6d96b6, 285f83e1cf484ff727d540c91e19aa5bff02ed31, 3d6be14bce5d15cd3437103c4738782fcd5b91bf

Credits: Ian Bottomley (@kyloe), Michael Wieland (@Programie)

## HTTP improvements

Usage of requests.Session()-objects may speed up the http communication by allowing HTTP keepalive and pooling.  By now it's also possible to pass ssl_cert in the connection parameters, for proper verification of self-signed certificates.

Github issues: https://github.com/python-caldav/caldav/pull/137, https://github.com/python-caldav/caldav/pull/110, https://github.com/python-caldav/caldav/pull/105

Commits: 917b17633d76f947c1778defa55ba680625b8fe4, 17ce1955ee6c233320a32cd61d24b9d9f3781e86, 6aa26c3bd497d6d6c0c3e6cceda4d02e25f31c74

Credits: Herve Commowick (@vr), Jelmer Vernooĳ (@jelmer), Stephan (@kiffie)

## Various bugfixes

Github issues: https://github.com/python-caldav/caldav/issues/112 https://github.com/python-caldav/caldav/issues/133

Commits: ed89a5911e1e9ba38302fef5febc5f03906f84bd, 3d0666d332d6505761488a04324c11257b7ed532, 576fd176c3ef64db973f059000976b7cc8c97d8c, 

Credits: Mincheol Song (@mtorange), @pleasedonotwatch, @frank-pet

## Refactoring work

Some major refactoring work has been done.  I've been consolidating lots of similar-looking code in previous releases, but it has been sort of "cargo-cult copying", I never bothered to really understand the lxml.etree module, nor to dig deeper into the details in the XML communication going on.  Basic XML response parsing has now been moved to the DAVResponse class, the response parsing should be a little bit easier to understand and debug, a little bit more robust, and I also made the API for fetching properties simpler to understand.  A lot of testing has been done, the "pure" unit test has been split out to a separate file, this includes lots of XML response snippets observed from the various server implementations and expectations on how they should be parsed.

Github issues: https://github.com/python-caldav/caldav/issues/118 https://github.com/python-caldav/caldav/issues/121

Commits: 3754d13270a5326a595c7ad290ebdf003f6d96b6, d5c17b522bef2e62038528f609fe320e91720f87, bc589093a34f0ed0ef489ad5e9cba048750c9837, 98a73ae2f948ca70d3425d5aeb52afff63d0def6, 552ff4728a191610d08f31a181573fb1f57e8692 e5968d0faa6852440f27ea23778a96814bef95fd 60ec379725b3ffedf57f33e869b15a4abf09464d, 951b878d44fa2d1d11bd1a5dd9b56d2f57b0179a, 02e5aa9358f65534077fa6e4c72d112faa05adb6

## Improvements on the test framework

Github issues: https://github.com/python-caldav/caldav/issues/136, https://github.com/python-caldav/caldav/issues/117 https://github.com/python-caldav/caldav/issues/2

Commits: 9dceb43c9abb32e98c948b49caf73eb24ae9d56f, 3ee4e42e2fa8f78b71e5ffd1ef322e4007df7a60, bc589093a34f0ed0ef489ad5e9cba048750c9837, 98a73ae2f948ca70d3425d5aeb52afff63d0def6 e5968d0faa6852440f27ea23778a96814bef95fd, 62b160aa39d260cd2ecf7ca6e2fb84454ebd2575 610fe1ccae88ec614f08081b3ae884734636fb35, 471c0741ca13c3e4006104db6fa52c5acd6515d8

Credits: @frank-pet
