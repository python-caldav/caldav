# Contributing

Contributions are mostly welcome (but do inform about it if you've used AI or other tools).  If the length of this text scares you, then I'd rather want you to skip reading and just produce a pull-request in GitHub.

## Git commit messages

Starting from v3.0.1, we'll stick to https://www.conventionalcommits.org/en/v1.0.0/ on the master branch.  A good pull request contains one commit that follows the conventions.  Otherwise the maintainer will have to rewrite the commit message.

The types used should (as for now) be one of:

* "revert" - a clean revert of a previous commit (should be used infrequently on the master branch)
* "feat" - a new feature added to the codebase/API.  The commit should include test code, documentation and a CHANGELOG entry unless there are good reasons for procrastinating it.  "feat" should not be used for new features that only affects the test framework, or changes only affectnig the documentation etc.
* "fix" - a bugfix.  Again, documentation and CHANGELOG-entry should be included in the commit (notable exception: if a bug was introduced after the previous release and fixed before the next release, it does not need to be mentioned in the CHANGELOG).  If the only "fix" is that some typo is fixed in some existing documentation, then we should use "docs" instead.
* "perf" - a code change in the codebase that is neither a bugfix or a feature, but intends to improve performance.
* "refactor" - a code change in the codebase that is neither a bugfix or a feature, but makes the code more readable, shorter, better or more maintainable.
* "test" - fixes, additions or improvements that only affects the test code or the test framework.  The commit may include documentation.
* "docs" - changes that *only* is done to the documentation, documentation framework - this includes minor typo fixes as well as new documentation, and it includes both the user documentation under `docs/source`, other documentation files (including CHANGELOG) as well as inline comments and docstrings in the code itself.
* "other" - if nothing of the above fits

This is not set in stone.  If you feel strongly for using something else, use something else in the commit message and update this file in the same commit.

"Imperative mood" is to be used in commit messages.

The boundaries of breaking changes vs "non-breaking" changes [may be blurry](https://xkcd.com/1172/). In the CHANGELOG I've used the concept "potentially breaking changes" for things that most likely won't break anything for anyone.  Potentially breaking changes should be marked with `!` in the commit header.  Breaking changes should be marked both with `!` and `BREAKING CHANGE:`

The conventionalcommits guide also says nothing about how to deal with security-relevant changes.  Maybe it makes sense to start the commit message (after the  "SECURITY: "

As for now, we do not use the module field. If there is strong reasons for using it, then go ahead and update this file in the same commit.

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
