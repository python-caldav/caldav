# HOWTO make a new release [DRAFT]

## Note

I have no clue on the proper procedures for doing releases, and I keep on doing clumsy mistakes - hence the need for this document.  Anyway, perhaps there are better ways of doing releases?  Feel free to shout out (or write up a pull-request).  (Indeed - in all other projects now I'm just tagging a release and then magic happens through CI pipelines.  I should consider the same for the caldav library)

(And no - we cannot do auto-releases of CalDAV.  Every release has to be well-tested, some of the tests needs my private configuration with passwords and usernames for various caldav servers, and some of the docker containers included are sluggish, full test runs takes very long time).

## Checklist

* Go through changes since last release and compare it with the `CHANGELOG.md`.  Any change should be logged.
* Run tests towards as many servers as possible
  * Use the `PYTHON_CALDAV_DEBUGMODE=DEBUG_PDB` environment variable (or simply pass `--pdb` to pytest, which sets this automatically)!  Should do some research if we hit any "soft asserts" or "weirdness".
  * Do research on breakages.  If the test breaks also for the previous release of the caldav library, then it's likely to be due to some regression on the server side.  For patch-level releases such breakages may be allowed, for minor-level releases we should try to work around problems
  * It's proper to document somewhere (TODO: where?  how?) what servers have been tested
* Does any of the changes require documentation to be rewritten?  The documentation should ideally be in sync with the code upon release time.
* Look through github pull requests and see if there is anything that ought to be included in the release
* For minor and major releases, look through the github issues, anything urgent there that should be fixed prior to doing a new release?
* Any changes done, go back to the start of this list
* Write up some release notes.  (I typically keep a short summary of the changes in the CHANGELOG, and use that as the release notes).
* Verify that we're on the right branch - `git checkout master`.  (`master` may not always be right - sometimes we may want to use a dedicated branch connected to the release-series, i.e. `v1.3`)
* TODO - document needs to be updated - as the test runs on github now takes significant amounts of time, it's important to push the code first and wait for quite a while before tagging and pushing the tag.
* Set the variable `VERSION=2.2.0`
* Commit the changes (typically `CHANGELOG.md`, perhaps documentation): `git commit -am "docs: preparing for v${VERSION}"`
* Create a tag: `git tag -as v${VERSION}` - use the release notes in the tag message.  Don't push it yet.
* Make a clone: `cd ~ ; rm -rf caldav-release ; git clone caldav/ caldav-release ; cd caldav-release ; git checkout v${VERSION}`
* Run tests: `pytest --pdb ; tox -e style`.
* Push the code to github: `cd ~/caldav ; git push ; git push --tags`
* The most important part - push to pypi.
  ```
  python3 -m venv ~/caldav-release-venv
  . ~/caldav-release-venv/bin/activate
  pip install -U pip build twine tox
  cd ~/caldav-release
  tox -e package     # builds sdist+wheel and fails if anything untracked is in them
  python -m build
  python -m twine upload dist/*
  ```
  `tox -e package` is the safety net for this whole class of mistake: it
  compares the sdist file list against `git ls-files` and refuses anything git
  does not track.  It runs in CI too, but run it here as well - CI checks the
  *repository*, this checks the *tree you are about to upload*.
* Some people rely on the github release system for finding releases, so it's needed to make a release there too.  Run `~/bin/github_push_release.py` or https://github.com/python-caldav/caldav/releases/new
* Remove the release dir and its venv: `rm -r ~/caldav-release ~/caldav-release-venv`
* Currently we have a policy that a 3.x.ya1 release should be made without the niquests dependency.  There exists a branch `niquests-less`.  Detailing the steps is TODO, probably we'll go over to trusted publishing before the next release.

## List of mistakes to be avoided

This is most likely not complete, but should explain some of the "silly" steps above ...

* Forgetting to set a release git tag
* Forgetting to update the version number (or setting it wrongly) - but now `setuptools-scm` is supposed to take care of that)
* Doing last-minute changes in i.e. `CHANGELOG.md` causing the style test to break
* Forgetting to add new files to the git repo
* Having checked out a branch or tag or something, and tagging that as the new release rather than the latest HEAD.
* Forgetting to push to pypi, or pushing something else than the tagged revision to pypi
* Pushing out junk files in the pypi-release (i.e. .pyc-files, log files, temp files, `tests/conf_private.py`, `tests/caldav_test_servers.yaml`, an entire `venv/`, etc).  `tox -e package` now catches this - see the build step above
* Not adding the release to the "github releases" (I don't care much about this feature, but apparently some people check there to find the latest release version)
