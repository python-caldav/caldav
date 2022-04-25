# Changelog v0.8.2 -> v0.9

## API changes

`save_todo`, `save_event` and `save_journal` now takes extra parameters, assumed to be equivalent with ical attributes as defined in the icalendar library, and may build icalendar data from scratch or enhance on the given icalendar data.

Added a context manager, so one can do `with DAVClient(foo) as client: ...`

Github issues: https://github.com/python-caldav/caldav/issues/156 https://github.com/python-caldav/caldav/issues/155 https://github.com/python-caldav/caldav/issues/175

Commits: eb8b7f877f4c5ca6181a177431b4a57f0a8c2039 b32f3ef3e15cd5edacca0ddaa9240c3814bc88ad fe108599167a517c56411d0bac9abb3abae8e825 ae2e71b1f0

Credits: @Sigmun @neonfighter28

## Refactoring

The digest vs basic auth is solved a bit differently in 0.8.2 and 0.9.  It has been fixed very carefully but inelegantly in 0.8.2, 0.9 contains a complete rewrite.

Github issues: https://github.com/python-caldav/caldav/issues/158

Commits: 1366e4e503180e10696f99ede6c2526451c7acab b3bde1c0e79d850acd5fa0615d3fbf6a3289c148 6be182800bbf7367a8da1005dad4b3e0b43967ca 164f88d

## Bugfixes and test framework

* Quite some problems fixed with the authentication code
* The string representation of any error class was hardcoded as "AuthorizationError".
* Concatinating an empty unicode string with an empty byte string will cause an exception.  The python_utilities.to_wire method would return an empty unicode string if given an empty unicode string.
* the flags no_overwrite and no_create in save_todo and save_journal didn't work
* scheduling still doesn't work very well, but one bug has been fixed
* tests and compatibility lists: some tweaks to let tests pass on the test servers (including fastmail)
* tests: make sure to delete the test calendar properly
* tests: test that non-base-urls still work
* tests: working around some issues on xandrikos startup, allows newer xandrikos version to be used
* tests: added flag "enable" in the test server config file

Github issues: https://github.com/python-caldav/caldav/issues/163 https://github.com/python-caldav/caldav/issues/164 https://github.com/python-caldav/caldav/issues/165 https://github.com/python-caldav/caldav/issues/166 https://github.com/python-caldav/caldav/issues/168 https://github.com/python-caldav/caldav/issues/169 https://github.com/python-caldav/caldav/issues/171 https://github.com/python-caldav/caldav/pull/176 https://github.com/python-caldav/caldav/pull/178  https://github.com/home-assistant/core/issues/65941 https://github.com/home-assistant/core/issues/65588 and many other issues on the home-assistant project

Commits: eb708a9 232acdd 509b4f01 67e47bc 29e2dd3 bafa810 dd26017 1de95ce1f ce89561bf 9aa31802 872232 52870b10 fa55194457a6f4 266a822e77 ce7c20527034f1 53da5d86c9cb 1d63ea77 4628bbc

Credits: Bjoern Kahl, Markus Behrens, Michael Thingnes
