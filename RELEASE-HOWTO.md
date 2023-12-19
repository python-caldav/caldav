# HOWTO make a new release [DRAFT]

## Note

I have no clue on the proper procedures for doing releases, and I keep on doing clumsy mistakes - hence the need for this document.  Anyway, perhaps there are better ways of doing releases?  Feel free to shout out (or write up a pull-request).

## Checklist

* Go through changes since last release and compare it with the `CHANGELOG.md`.  Any change should be logged.
* Run tests towards as many servers as possible
  * On breakages, record an issue, check if the previous release also breaks.  If so, the breakage is most likely due to server changes.  For patch-level releases we don't care about such breakages, for minor-level releases we should try to work around problems
  * It's proper to document somewhere (TODO: where?  how?) what servers have been tested
* Does any of the changes require documentation to be rewritten?  The documentation should ideally be in sync with the code upon release time.
* Look through github pull requests and see if there is anything that ought to be included in the release
* For minor and major releases, look through the github issues, anything urgent there that should be fixed prior to doing a new release?
* Write up some release notes.  (I typically keep a short summary of the changes in the CHANGELOG, and use that as the release notes).
* Verify that we're on the right branch - `git checkout master`.  (`master` may not always be right - sometimes we may want to use a dedicated branch connected to the release-series, i.e. `v1.3`)
* Commit the changes (typically `CHANGELOG.md`, `__init__.py`, documentation): `git commit -am "preparing for releasing v${VERSION}`
* Create a tag: `git tag -as v${VERSION}` - use the release notes in the tag message.
* Make a clone: `git clone caldav/ caldav-release ; cd caldav-release ; git checkout v${VERSION}`
* Run tests (particularly the style check): `pytest` and `tox -e style`.
* Push the code to github: `cd ~/caldav ; git push ; git push --tags`
* Some people relies on the github release system for finding releases - go to https://github.com/python-caldav/caldav/releases/new, choose the new tag, copy the version number and the release notes in.
* The most important part - push to pypi:
  ```
  cd ~/caldav-release
  python3 -m venv venv
  . venv/bin/activate
  pip install -U pip build twine
  python -m build
  python -m twine upload dist/*
  ```
