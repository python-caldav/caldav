# HOWTO make a new release [DRAFT]

## Note

I have no clue on the proper procedures for doing releases, and I keep on doing clumsy mistakes - hence the need for this document.  Anyway, perhaps there are better ways of doing releases?  Feel free to shout out (or write up a pull-request).  (Indeed - in all other projects now I'm just tagging a release and then magic happens through CI pipelines.  There is a workflow for doing the same here, but it cannot be switched on yet - see "Publishing from CI" below.)

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
* Set the variable `VERSION=3.3.1`
* Commit the changes (typically `CHANGELOG.md`, perhaps documentation): `git commit -am "preparing for releasing v${VERSION}"`
* Push the code to github - `git push` - and **wait for the test runs to go
  green** before tagging.  They take a good while, and this is the last point
  where a mistake is still cheap.
* Create a tag: `git tag -as v${VERSION}` - use the release notes in the tag message.  Don't push it yet.
* Make a clone: `cd ~ ; git clone caldav/ caldav-release ; cd caldav-release ; git checkout v${VERSION}`
* Run tests (particularly the style check): `pytest` and `tox -e style`. TODO: is `tox -e style` still relevant?
* Push the tag: `cd ~/caldav ; git push --tags`
* Some people relies on the github release system for finding releases - go to https://github.com/python-caldav/caldav/releases/new, choose the new tag, copy the version number and the release notes in.  Remember to check the box to make it the latest release.
* The most important part - push to pypi.  Note that the virtualenv is created
  *outside* the release clone: `python -m build` packages the directory it is
  pointed at, and a venv sitting inside it goes straight into the tarball.
  That is how `caldav-3.2.1.tar.gz` came to contain 1755 files under `venv/`.
  ```
  python3 -m venv ~/caldav-release-venv
  . ~/caldav-release-venv/bin/activate
  pip install -U pip build twine tox packaging
  cd ~/caldav-release
  tox -e package     # builds sdist+wheel and fails if anything untracked is in them
  python -m build
  python tests/tools/check_release_version.py dist --tag v${VERSION}
  python -m twine upload dist/*
  ```
  `tox -e package` is the safety net for this whole class of mistake: it
  compares the sdist file list against `git ls-files` and refuses anything git
  does not track.  It runs in CI too, but run it here as well - CI checks the
  *repository*, this checks the *tree you are about to upload*.

  `check_release_version.py` is the second safety net: it reads the version out
  of the artifacts' own metadata and refuses to let a `3.3.1.dev4+g1234567` -
  which is what `hatch-vcs` produces from a checkout that is not exactly on the
  tag - be uploaded under the impression that it is `3.3.1`.
* Remove the release dir and its venv: `rm -r ~/caldav-release ~/caldav-release-venv`
* Publish the companion alpha - the `niquests`-free variant.  Since 3.3.0, every
  release has one, so that consumers who cannot pull in `niquests` (and the
  `urllib3_future.pth` it brings - see
  https://github.com/python-caldav/caldav/issues/690) have something to pin.
  **Tag it on a throwaway branch, never on the release branch:**
  ```
  git checkout -b tmp-${VERSION}a1 v${VERSION}
  ## drop "niquests" from [project] dependencies in pyproject.toml
  git commit -am "chore: build ${VERSION}a1 without the niquests dependency"
  git tag -as v${VERSION}a1
  ```
  then build and upload it exactly as above, from its own clean clone.  Push the
  tag (`git push origin v${VERSION}a1`) but **do not push or merge the branch**,
  and delete it locally afterwards.  The reason for the side branch is that
  `hatch-vcs` derives the version from the nearest tag: an `a1` tag sitting on
  the mainline as a descendant of `v${VERSION}` would make every subsequent dev
  version be computed from `${VERSION}a1`, which under PEP 440 sorts *below*
  `${VERSION}`.
* Two things to note in the release notes about the alpha:
  * it must be pinned exactly - `caldav==${VERSION}a1`.  A range such as
    `caldav>=${VERSION}a1` still resolves to the final release, since pip picks
    the highest eligible version.
  * it declares *no* HTTP library at all, so `pip install caldav==${VERSION}a1`
    on its own gives an installation that raises on the first `DAVClient`.  Its
    consumers have to bring their own `requests` (or anything else supported).

## Publishing from CI - written, not switched on

`.github/workflows/publish.yaml` does the whole mechanical half of the list
above - build, check the tarball for junk, check the version against the tag,
smoke-test the wheel, upload to PyPI, create the github release from the
annotated tag's message.  Both flavours of tag would go through it, the
companion alpha included: the workflow file comes from the tagged tree, so the
throwaway branch's `pyproject.toml` is what gets built.

It is deliberately **not** triggered by tags.  It only runs on
`workflow_dispatch`, where it stops after the checks and publishes nothing, so
it can be exercised without a PyPI account being involved at all.

What it is waiting for is [trusted publishing](https://docs.pypi.org/trusted-publishers/),
which has to be configured under the PyPI project's settings - and those are
the *owner's* to change, which for `caldav` is Cyril, not me.  The publisher to
register is:

| field | value |
| --- | --- |
| Owner | `python-caldav` |
| Repository name | `caldav` |
| Workflow name | `publish.yaml` |
| Environment name | `pypi` |

The fallback, if that stays out of reach, is a project-scoped PyPI API token
held as a github secret bound to the `pypi` environment; anyone with upload
rights can mint one of those without owning the project.  It is strictly worse
than OIDC - a long-lived credential sitting in github rather than no credential
at all - so it is worth asking first.

When switching it on:

* add the tag trigger back:
  ```yaml
  on:
    push:
      tags:
        - "v[0-9]+.[0-9]+.[0-9]+*"
    workflow_dispatch:
  ```
  The `if: github.event_name == 'push'` guard on the publish job should stay,
  so that `workflow_dispatch` remains a dry run.
* tick *Required reviewers* on the `pypi`
  [github environment](https://github.com/python-caldav/caldav/settings/environments).
  Then a tag push stops before the upload and waits for a human to click
  Approve, and a build that looks wrong can be rejected.  Rejecting is free; a
  PyPI upload is forever, and automating the upload is otherwise a step *away*
  from the safety the manual flow has.
* implement the tag signature check below, in the same change.
* delete the manual pypi steps from the checklist above, not before.

## Verifying the tag signature - not implemented yet

Once the workflow does publish on tags, anyone who can push a tag to the
repository can publish to PyPI.  The intended guard is to verify, before
anything is built, that the tag carries a good signature from a key we know:

```yaml
      - name: Verify the tag signature
        if: github.ref_type == 'tag'
        env:
          TAG: ${{ github.ref_name }}
        run: |
          gpg --import .github/release-signing-keys.asc
          git verify-tag "$TAG"
```

with the maintainer's public key committed as
`.github/release-signing-keys.asc`.  Notes for whoever implements it:

* `git verify-tag` exits non-zero on an unsigned or lightweight tag, which is
  the behaviour we want - `git tag -as` is already the documented way to tag.
* the key has to be committed to the repository (or held in a repository
  *variable*, not a secret - it is public, and secrets are not available to
  the workflow when it needs to fail closed).  Committing it makes the trust
  root reviewable in the history.
* a good signature from *some* key in the keyring is not enough; pin the
  fingerprint, or import exactly the one key.
* if signing ever moves to ssh keys, `git verify-tag` needs
  `gpg.ssh.allowedSignersFile` pointing at a committed allowed-signers file
  instead.

Not urgent while the workflow cannot publish, but it must land together with
the tag trigger.

## List of mistakes to be avoided

This is most likely not complete, but should explain some of the "silly" steps above ...

* Forgetting to set a release git tag
* Forgetting to update the version number (or setting it wrongly) - but now `hatch-vcs` is supposed to take care of that)
* Doing last-minute changes in i.e. `CHANGELOG.md` causing the style test to break
* Forgetting to add new files to the git repo
* Having checked out a branch or tag or something, and tagging that as the new release rather than the latest HEAD.
* Tagging before the github test runs have gone green
* Forgetting to push to pypi, or pushing something else than the tagged revision to pypi
* Pushing out junk files in the pypi-release (i.e. .pyc-files, log files, temp files, `tests/conf_private.py`, `tests/caldav_test_servers.yaml`, an entire `venv/`, etc).  `tox -e package` now catches this - see the build step above
* Building from a tree that is not exactly on the tag, so that a `.dev` version gets uploaded.  `tests/tools/check_release_version.py` catches this
* Forgetting the companion `a1` release, or tagging it on the release branch instead of a throwaway one (which poisons every later dev version number)
* Not adding the release to the "github releases" (I don't care much about this feature, but apparently some people check there to find the latest release version)
