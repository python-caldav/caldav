# Contributing

Contributions are mostly welcome.  If the length of this text scares you, then I'd rather want you to skip reading and just produce a pull-request in GitHub.

## Usage of AI and other tools

A separate [AI POLICY](AI-POLICY.md) has been made.  The gist of it, be transparent and inform if your contribution was a result of clever tool usage and/or AI-usage, don't submit code if you don't understand the code yourself, and you are supposed to contribute value to the project.  If you're too lazy to read the AI Policy, then at least have a chat with the AI to work out if your contribution is within the policy or not.

## GitHub

The official guidelines currently involves contributors to have a GitHub account - but this is not a requirement!  If you for some reason or another don't want to use GitHub, then that's fine.  Reach out by email, IRC, matrix, signal, deltachat, telegram or whatnot.

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

## Code of Conduct

Code of Conduct has been moved to a [separate document](CODE_OF_CONDUCT]
