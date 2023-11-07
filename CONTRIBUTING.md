# Contributing

Contributions are mostly welcome.  If the length of this text scares you, then I'd rather want you to skip reading and just produce a pull-request in GitHub.

## Considerations

* Contributions that break backward compatibility will (generally) not be accepted
* Primary scope of the library is to deal with the CalDAV-protocol.  Just consider for a moment if your new feature may fit better into another library, like the icalendar library or the plann tool.
* Workarounds for supporting some quirky CalDAV-server is generally accepted, just be careful that your contribution does not break for other CalDAV-servers.
* If you need to deal with iCalendar payload, new code should do it through the icalendar library.

## Contribution Procedure

Consider this procedures to be a more of a guideline than a rigid procedure.  Use your own judgement, skip steps you deem too difficult, too boring or that doesn't make sense.  If you don't have an account at GitHub, then reach out by email to t-py-caldav@tobixen.no (prepend subject with `caldav:` and my spam filter will let it through).

* Write up an issue at [GitHub](https://github.com/python-caldav/caldav/issues/new)

* Create your own [GitHub fork](https://github.com/python-caldav/caldav/fork)

* Clone locally (`git clone https://github.com/$LOGNAME/caldav`) and run `pytest` for a quick run of the tests.  They should pass (you may need to replace `$LOGNAME`).

* Write up some test code prior to changing the code ("test-driven development" is a good concept)

* Write up your changes

* Run `pytest` for a quick run of the tests.  They should still pass.

* Run `tox -e style` to verify a consistent code style (this may modify your code).

* Consider to write some lines in the documentation and/or examples covering your change

* Add an entry in the `CHANGELOG.md` file.

* Create a pull request
```

## Code of Conduct

I hope it will never be needed, but eventually at some point perhaps some stuff from https://www.contributor-covenant.org/ will be copied in here.
