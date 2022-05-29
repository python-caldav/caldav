# Changelog v0.9.0 -> v0.9.1

## Minor changes

* Quite some users are complaining because recurring events aren't supported - which is intentional, because the server is supposed to take care of that.  Unfortunately quite some servers doesn't.  Thanks to cos, at least we now have some code in place to log an error (or optionally raising an error) when recurrences aren't taken care of (though, it only works if the server is returning non-expanded recurring events - if searching for a recurrence and the server doesn't find it, then ... no error logged).  The error message is referring to https://github.com/python-caldav/caldav/issues/157
* New method `.close` on the DAVClient object

Credits: |cos|, neonfighter28

commits: 53c74737fd83b32e016a954b7b5f57bb028e0f24 c20ed6a65acae6c4e1cdd0fa2b9dc73244932681 ddcd11508290b0dbc580dde0f2aa712d95d1e6f7 99494d160e5363dd3e29cbbea9889521665b64a4 0ce851d0baedea70069df780e525a7aafda5aa5c

## Documentation fixes

* Added the fastmail caldav URL to the documentation - including note that they are picky on the trailing slash - ref https://github.com/home-assistant/core/issues/66599
* Keeping the changelog up-to-date

commits: ec29395beb27dfa734078195b29685563c284cbc ea4fb0845343436fd5f4cb65852ee1437505ae58 fcb616d7f6016d65bc79dbae7f131d049fa1522d d43fbdde507a642dd5a55facc6bbea4b372e786b

credits: Martin Eberhardt

## Bugfixes

* v0.9.0 broke on elder python versions due to an f"string".  The f-format was introduced in python 3.6.  Anything below is actually End of Life versions, but still ... it's a very small effort here to preserve compatibility with elder python versions.
* The library had some difficulties with the DAVMail server - at one point it does not return a calendar home set property, and at another point the calendar home set URL is the same as the calendar URL.
* The `URL.canonical()` method should rewrite variants of the same URL into something that will be equal - some work has been put making it more robust.

Credits: |cos|, Jonathan Neuhauser <jonathan.neuhauser@kit.edu>

Commits: a82cb81d02fe207106951cdecd49fefc8146155a 1ab5b9926c372af8f5644908d523e3b47fa3f9c1 2aae381f2cb499f203a994d217ce989a8d97071e 0e224be5818b2392402d6e5cc593d94655eb06d0 e5b5fa2c829d0d79f42adb45c5f2ce4aba7d9496 e5b5fa2c829d0d79f42adb45c5f2ce4aba7d9496 9f8786acd6cce506235da80b9d8438c6354e91bc 8dd2094471bac3cd17f3f9fb5570afd1ffdf1729 49f70bcb245aac8411e5c8942e91145342257fa3

Issues: https://github.com/python-caldav/caldav/issues/189.  f-strings discussed outside github.

## Linting

Removal of some extra white space

Credits: |cos|

commits: 783e233cf8c86fb87fef0245841edd86e392efb3

## Testing framework and incompatibility matrix

* The testTodoDatesearch is pesky - because every server has different visions on how (or weather) to support recurring tasks

commits 7bdb32498582477a8b8bd45a871d441711356903

# Changelog v0.8.2 -> v0.9

## API changes

`save_todo`, `save_event` and `save_journal` now takes extra parameters, assumed to be equivalent with ical attributes as defined in the icalendar library, and may build icalendar data from scratch or enhance on the given icalendar data.

Added a context manager, so one can do `with DAVClient(foo) as client: ...`

Github issues: https://github.com/python-caldav/caldav/issues/156 https://github.com/python-caldav/caldav/issues/155 https://github.com/python-caldav/caldav/issues/175

Commits: eb8b7f877f4c5ca6181a177431b4a57f0a8c2039 b32f3ef3e15cd5edacca0ddaa9240c3814bc88ad fe108599167a517c56411d0bac9abb3abae8e825 ae2e71b1f0

Credits: @Sigmun @neonfighter28

## Refactoring

The digest vs basic auth is solved a bit differently in 0.8.2 and 0.9.  It has been fixed very carefully but inelegantly in 0.8.2, 0.9 contains a complete rewrite.  It was later shown that the logic in 0.8.2 broke for some servers, hence I've decided to discontinue support for the 0.8-branch.

Github issues: https://github.com/python-caldav/caldav/issues/158

Commits: 1366e4e503180e10696f99ede6c2526451c7acab b3bde1c0e79d850acd5fa0615d3fbf6a3289c148 6be182800bbf7367a8da1005dad4b3e0b43967ca 164f88d

## Bugfixes and test framework

This release does not fix a reported regression at https://github.com/home-assistant/core/issues/65588 (and probably some other places) that iCloud caldav URLs pointing directly to a calendar won't work.  I'm not sure if this is a regression in the caldav library or in Home Assistant.  I've written up test code to catch this issue, but didn't have an iCloud account available to test with while releasing.

This release does not fix a reported possible regression in Home Assistant that public ICS feeds does not work anymore as the "caldav URL".  I don't think such an URL ever was working with the caldav library, I believe it's needed with some extra logic in the Home Assistant module if public ics feeds are to be supported.  (issues https://github.com/home-assistant/core/issues/70205 https://github.com/home-assistant/core/issues/65941)

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

Github issues: https://github.com/python-caldav/caldav/issues/163 https://github.com/python-caldav/caldav/issues/164 https://github.com/python-caldav/caldav/issues/165 https://github.com/python-caldav/caldav/issues/166 https://github.com/python-caldav/caldav/issues/168 https://github.com/python-caldav/caldav/issues/169 https://github.com/python-caldav/caldav/issues/171 https://github.com/python-caldav/caldav/pull/176 https://github.com/python-caldav/caldav/pull/178 https://github.com/home-assistant/core/issues/67330 https://github.com/home-assistant/core/issues/71048 https://github.com/home-assistant/core/issues/65804

Commits: eb708a9 232acdd 509b4f01 67e47bc 29e2dd3 bafa810 dd26017 1de95ce1f ce89561bf 9aa31802 872232 52870b10 fa55194457a6f4 266a822e77 ce7c20527034f1 53da5d86c9cb 1d63ea77 4628bbc

Credits: Bjoern Kahl, Markus Behrens, Michael Thingnes
