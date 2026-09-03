# HOWTO make a new release

## Note

Releases are cut by hand and published by CI.  The manual part is the part
that needs judgement - deciding that the code is ready, and against which
servers it has been tested.  Everything mechanical (building, checking the
tarball for junk, uploading to PyPI, creating the github release) is done by
the `publish` workflow, triggered by pushing a signed tag.

We cannot do auto-releases of CalDAV.  Every release has to be well-tested,
some of the tests need private configuration with passwords and usernames for
various caldav servers, and some of the docker containers included are
sluggish - full test runs take a very long time.

## Before tagging

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
* Push the code and **wait for the github test runs to go green** before
  tagging.  They take a while, and the tag is the point of no return.

## Cutting the release

```
VERSION=3.3.1
git commit -am "preparing for releasing v${VERSION}"
git push
## wait for CI on master to go green
git tag -as v${VERSION}           # the tag message becomes the release notes
git push origin v${VERSION}
```

That is the whole release.  Pushing the tag starts `.github/workflows/publish.yaml`,
which:

1. builds the sdist and the wheel and runs `tox -e package` over them, so
   nothing untracked by git can ride along into the tarball;
2. checks that the version the artifacts carry is exactly the tag
   (`tests/tools/check_release_version.py`) - this is what stops a
   `3.3.1.dev4+g1234567` from being published by accident;
3. installs the built wheel in a clean environment and runs the server-less
   tests;
4. uploads to PyPI over [trusted publishing](https://docs.pypi.org/trusted-publishers/) -
   no API token exists anywhere;
5. creates the github release, with the annotated tag's message as the release
   notes and the artifacts attached.

The tag message is therefore the release notes - write it as such.

### The niquests-free companion alpha

Since 3.3.0, every release has a companion `a1` that does not depend on
`niquests`, so that consumers who cannot pull in `niquests` (and the
`urllib3_future.pth` it brings - see
https://github.com/python-caldav/caldav/issues/690) have something to pin.

**Tag it on a throwaway branch, never on the release branch:**

```
git checkout -b tmp-${VERSION}a1 v${VERSION}
## drop "niquests" from [project] dependencies in pyproject.toml
git commit -am "chore: build ${VERSION}a1 without the niquests dependency"
git tag -as v${VERSION}a1
git push origin v${VERSION}a1     # the tag only - never the branch
git checkout master
git branch -D tmp-${VERSION}a1
```

The same workflow picks this up and publishes it: the workflow file comes from
the tagged tree, so it builds whatever `pyproject.toml` that branch carries.
Pushing the tag pushes the commit it points at, which is all github needs; the
branch itself must not be pushed or merged, because `hatch-vcs` derives the
version from the nearest tag, and an `a1` tag sitting on the mainline as a
descendant of `v${VERSION}` would make every subsequent dev version be computed
from `${VERSION}a1` - which under PEP 440 sorts *below* `${VERSION}`.

Two things to note in the release notes:

* the alpha must be pinned exactly - `caldav==${VERSION}a1`.  A range such as
  `caldav>=${VERSION}a1` still resolves to the final release, since pip picks
  the highest eligible version.
* the alpha declares *no* HTTP library at all, so `pip install caldav==${VERSION}a1`
  on its own gives an installation that raises on the first `DAVClient`.  Its
  consumers have to bring their own `requests` (or anything else supported).

## Rehearsing the workflow without burning a version number

The `publish` workflow can be started by hand from the Actions tab
(`workflow_dispatch`).  Everything up to and including the smoke test runs;
the publish and github-release jobs are skipped, because they are guarded on
the event being a tag push.  Use this after editing the workflow.

The second safety net is the `pypi` [github environment](https://github.com/python-caldav/caldav/settings/environments)
the publish job runs in.  Tick *Required reviewers* there and a tag push stops
before the upload and waits for a human to click Approve - so a build that
looks wrong can be rejected, and the version number survives.  Rejecting an
approval is free; a PyPI upload is forever.

## One-time setup (done once, documented for the record)

Trusted publishing has to be configured on PyPI, at
https://pypi.org/manage/project/caldav/settings/publishing/ :

| field | value |
| --- | --- |
| Owner | `python-caldav` |
| Repository name | `caldav` |
| Workflow name | `publish.yaml` |
| Environment name | `pypi` |

The environment name must match the `environment:` in the workflow, and the
`pypi` environment must exist on the github side too (it is created
automatically on the first run, but create it up front if you want required
reviewers from the start).

## Verifying the tag signature - not implemented yet

The workflow currently trusts any tag that matches the pattern.  Anyone who can
push a tag to the repository can therefore publish to PyPI.  The intended fix is
to verify, before anything is built, that the tag carries a good signature from
a key we know:

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
  the workflow when it needs to fail closed).  Committing it makes the
  trust root reviewable in the history.
* a good signature from *some* key in the keyring is not enough; pin the
  fingerprint, or import exactly the one key.
* if signing ever moves to ssh keys, `git verify-tag` needs
  `gpg.ssh.allowedSignersFile` pointing at a committed allowed-signers file
  instead.

Deferred to the next patch release, deliberately - it is worth getting the
publishing path working first, and the required-reviewers gate on the `pypi`
environment covers the same ground in the meantime.

## List of mistakes to be avoided

This is most likely not complete, but should explain some of the "silly" steps above ...

* Forgetting to set a release git tag
* Forgetting to update the version number (or setting it wrongly) - but now `hatch-vcs` is supposed to take care of that)
* Doing last-minute changes in i.e. `CHANGELOG.md` causing the style test to break
* Forgetting to add new files to the git repo
* Having checked out a branch or tag or something, and tagging that as the new release rather than the latest HEAD.
* Tagging before the github test runs on master have gone green
* Pushing out junk files in the pypi-release (i.e. .pyc-files, log files, temp files, `tests/conf_private.py`, `tests/caldav_test_servers.yaml`, an entire `venv/`, etc).  `tox -e package` catches this, in the publish workflow and nightly
* Forgetting the companion `a1` release, or tagging it on the release branch instead of a throwaway one (which poisons every later dev version number)
* Building from a tree that is not exactly on the tag, so that a `.dev` version gets uploaded.  `tests/tools/check_release_version.py` catches this
