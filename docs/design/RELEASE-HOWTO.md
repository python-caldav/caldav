# HOWTO make a new release [DRAFT]

## Note

I have no clue on the proper procedures for doing releases, and I keep on doing clumsy mistakes - hence the need for this document.  Anyway, perhaps there are better ways of doing releases?  Feel free to shout out (or write up a pull-request).  (Indeed - in all other projects now I'm just tagging a release and then magic happens through CI pipelines.  I should consider the same for the caldav library)

(And no - we cannot do auto-releases of CalDAV.  Every release has to be well-tested, some of the tests needs my private configuration with passwords and usernames for various caldav servers, and some of the docker containers included are sluggish, full test runs takes very long time).

## One-off: after the switch to towncrier

3.5.0 was the last release whose `CHANGELOG.md` section was written by hand.  Branches and pull requests still carrying an entry in `CHANGELOG.md` need it moved into a fragment in `changes/` before they are merged.  Delete this section once none are left.

## Checklist

* Go through changes since last release and compare it with the changelog fragments in `changes/` (`towncrier build --draft --version X` shows them as they will end up in the `CHANGELOG.md`, see `changes/README.md`).  Any change should be logged.
* Run tests towards as many servers as possible
  * Use the `PYTHON_CALDAV_DEBUGMODE=DEBUG_PDB` environment variable (or simply pass `--pdb` to pytest, which sets this automatically)!  Should do some research if we hit any "soft asserts" or "weirdness".
  * Do research on breakages.  If the test breaks also for the previous release of the caldav library, then it's likely to be due to some regression on the server side.  For patch-level releases such breakages may be allowed, for minor-level releases we should try to work around problems
  * It's proper to document somewhere (TODO: where?  how?) what servers have been tested
* Does any of the changes require documentation to be rewritten?  The documentation should ideally be in sync with the code upon release time.
* Look through github pull requests and see if there is anything that ought to be included in the release
* For minor and major releases, look through the github issues, anything urgent there that should be fixed prior to doing a new release?
* Any changes done, go back to the start of this list
* Write up some release notes.  (I typically keep a short summary of the changes in the CHANGELOG, and use that as the release notes - see the `towncrier build` step below).
* Verify that we're on the right branch - `git checkout master`.  (`master` may not always be right - sometimes we may want to use a dedicated branch connected to the release-series, i.e. `v1.3`)
* TODO - document needs to be updated - as the test runs on github now takes significant amounts of time, it's important to push the code first and wait for quite a while before tagging and pushing the tag.
* Set the variable `VERSION=2.2.0`
* Collect the changelog fragments: `towncrier build --yes --version ${VERSION}` (`pip install towncrier`; without `--yes` it asks before removing the fragments).  It writes a `## [${VERSION}] - <date>` section into `CHANGELOG.md` at the `<!-- towncrier release notes start -->` marker and `git rm`s the fragments.  The date is the day of the build - fix it if the tag comes later.  The result is plain markdown - now edit it by hand: towncrier sorts the entries by issue number, so reorder them by importance, add the summary on top, and add the `[${VERSION}]: https://github.com/python-caldav/caldav/compare/vPREVIOUS...v${VERSION}` link at the bottom of the file.
* The new compare link 404s until the tag is pushed, and the code is pushed first, so the pre-push link check (lychee) refuses the push.  Add (or re-point) the compare-link entry in `.lycheeignore` ("The CHANGELOG compare link for the release being prepared"), naming `v${VERSION}` in its comment.  The entry is a regular expression, so escape the dots: `https://github\.com/python-caldav/caldav/compare/vPREVIOUS\.\.\.v${VERSION}`.  Commit it with the CHANGELOG.
* Commit the changes (typically `CHANGELOG.md` and the removed fragments, perhaps documentation): `git commit -am "docs: preparing for v${VERSION}"`
* Create a tag: `git tag -as v${VERSION}` - use the release notes in the tag message.  Don't push it yet.
* Make a clone: `cd ~ ; rm -rf caldav-release ; git clone caldav/ caldav-release ; cd caldav-release ; git checkout v${VERSION}`
* Run tests: `pytest --pdb ; tox -e style`.
* Push the code to github: `cd ~/caldav ; git push ; git push --tags`
* Once the tag is on GitHub, delete that `.lycheeignore` entry again, or the link check never notices if the compare link breaks.
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
* Some people rely on the github release system for finding releases, so it's needed to make a release there too.  Run `~/bin/github_push_release.py` or https://github.com/python-caldav/caldav/releases/new .  Or, with the notes taken from the tag annotation: `gh release create vX.Y.Z --verify-tag --title vX.Y.Z --notes-from-tag`, adding `--latest=false` for anything but the newest release and `--prerelease` for a0 releases.  `gh release edit` has no `--notes-from-tag`; to replace the notes of an existing release, use `git tag -l --format='%(contents:body)' vX.Y.Z | gh release edit vX.Y.Z --notes-file -` (the body leaves out the tag message's first line, which only repeats the version).
* Remove the release dir and its venv: `rm -r ~/caldav-release ~/caldav-release-venv`
* Currently we have a policy that every release is also made without the niquests dependency, as `X.Y.Za0` - see "Releases without niquests" below.

## Releases without niquests (`X.Y.Za0`)

*This section was written by Claude Opus and has not gone through human review or testing*

Each release is also published without the hard dependency on niquests, as a pre-release `X.Y.Za0` sorting just below `X.Y.Z`.  Users of it must install an HTTP library alongside it themselves: requests for the sync client, and/or httpx2 for the async client.

* Make a separate clone, and branch off the release: `git switch -c vX.Y-niquests-less vX.Y.Z`.
* Cherry-pick the commit `chore: remove niquests dependency`, the tip of the previous niquests-less branch (e.g. `git cherry-pick v3.5-niquests-less`).  It comments the dependency out in `pyproject.toml`; the `niquests` extra stays.
* Tag it `vX.Y.Za0` - not `vX.Y.Za`, which PyPI normalises to `a0` anyway and which then no longer matches the tag.
* After `python -m build`, check the wheel: `unzip -p dist/*.whl '*/METADATA' | grep Requires-Dist` must list niquests only with `extra == "niquests"`.
* Upload after the regular release; on GitHub, create the release with `--prerelease --latest=false`.
* Push the `vX.Y-niquests-less` branch along with the tag.

## Security releases

*This section was written by Claude Opus and has not gone through human review or testing*

Done the first time for GHSA-5h4q-xm57-3mh5 (3.3.2, 3.4.1 and 3.5.0, each also as a0).  The fix stays private until the release, so the normal "push first, let CI run" order is turned around.

Before the release:

* Develop the fix on a local branch that is never pushed, with a test that fails before the fix.  GitHub CI never sees it before release day, so run the unit tests locally on every release line instead (`pytest`, without the integration tests that need test servers).
* Keep the GitHub security advisory as a draft (it is private).  Set the affected ranges with `a0` bounds, so the fixed a0 releases fall outside them: `< 3.3.2a0` and `>= 3.4.0, < 3.4.1a0` - `< 3.3.2` would flag 3.3.2a0 as vulnerable.  A lower bound like `>= 3.4.0` leaves out pre-releases of 3.4.0, so check PyPI for those.  Fill in the patched versions, and a CVSS vector - with CVSS 4.0, "the attacker must control the server or a calendar the victim subscribes to" is `AT:P`.  Request the CVE while the advisory is still a draft, so the ID exists when it is published.
* Decide which release lines get a patch release: the newest of each maintained minor series.  Older ones are told to upgrade, in the advisory.
* Prepare the `CHANGELOG.md` on a local master that is not pushed before release day - pushing it leaks the fix.  Keep the security entry as a fragment that stays local, and run `towncrier build` for the new minor release (if any) and for each patch release, so that each section carries the security entry, in version order.  The a0 releases get one line in their regular release's section, not a section of their own.  This file is copied verbatim into every release line.

On release day - stop pushing to the repository from anywhere else:

* For each release line, a separate clone (`git clone ~/caldav ~/caldav-release-X.Y.Z` - a local clone carries the unpushed commits and tags), and for each patch release a branch from the line's last tag, e.g. `git switch -c v3.4-maint v3.4.0`; the new minor release is master itself.  Cherry-pick the fix with `-n`, take the CHANGELOG from master (`git checkout origin/master -- CHANGELOG.md`, which also resolves its conflict), and commit.
* QA in each clone, before tagging: `pytest` (without the server tests) and `tox -e style,package` (where the line has a `package` env).
* Tag each release signed, with its CHANGELOG section as the annotation: `git tag -s --cleanup=whitespace -F notes.txt vX.Y.Z`.  Without `--cleanup=whitespace`, git drops every `###` heading line from the message as a comment.
* The tags exist before anything is reviewed or pushed.  Any review step that rewrites commits afterwards (rewording a message, adding a trailer) leaves the signed tags pointing at commits that are no longer on the branches - record the review without rewriting, or re-tag.
* `python -m build` in each clone (the version comes from the tag), and check that every file name in `dist/` carries exactly the intended version.
* Upload the patch releases first, then the new minor release, so trouble with the latter cannot delay the fix.  Then check: the SHA-256 of each file on `https://pypi.org/pypi/caldav/<version>/json` against `dist/`, and `pip install caldav==<version>` in a fresh venv (the index can lag the upload by some minutes).
* Publish the advisory.
* Push master, the maintenance and niquests-less branches and all release tags, a0 ones included - by name, not with `git push --tags` (see the mistakes below).
* Create the GitHub releases as described in the checklist, with `--latest=false` for everything but the newest.
* Remove the release clones.

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
* Not committing after running `towncrier build` (or, up to and including 3.5.0, after doing a s/unreleased/$VERSION/ on the CHANGELOG)
* "Playing ball" with Claude on the CHANGELOG and committing the changes directly to master before a release, not going through the regular QA - and suddenly the master branch has 6-7 commits with various irrelevant prompts attached.
* `git push --tags` pushes every local tag, backup tags and experiments included - push release tags by name.
* Creating a GitHub release for an older version without `--latest=false`, so that it becomes the "Latest" release.
