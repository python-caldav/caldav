# Sans-GitHub

I'm not easy with being dependent on centralized components owned by third parties, GitHub being one of them.  GitHub is a Microsoft-owned, centralized, proprietary, US-based SaaS system, and due to the geopolitical situation an "exit strategy" has become important, at least for EU-based organizations.  Funders are paying attention too: NLnet, which funds parts of this project, may come to favour projects that avoid GitHub.  So we may have to move one day.

## It has happened before

The project has already moved platform once: it started on BitBucket and moved to GitHub, because GitHub was becoming the de facto standard.  That was before Microsoft bought GitHub.  Moving the issues over was a fair bit of hard manual work.  Today `git bug bridge pull` could do most of that, if only it worked (see below).

## Why the project is still on GitHub

I do want to move away from GitHub, but abandoning it has a real cost: the network effect.  Almost everybody is on GitHub.  Users find the project there, report issues there, and contributors can send a pull request without registering anywhere new.

I've considered the alternatives:

* **A self-hosted platform** (Forgejo, Gitea, GitLab CE): full control, but it costs maintenance and hosting, and every contributor would need an account on yet another server.
* **A European centralized service based on open source** (Codeberg): better than GitHub on ownership and jurisdiction, but it is still a centralized service, with a much smaller network.  Trading one centralized service with a good network effect for another one with only a fraction of the users does not look like a good deal.

So far my conclusion is that neither is worth the cost.  What would change the picture is a *federated* platform, where an account on one forge can file issues and pull requests on another (ForgeFed is working on this).  Anyone up for the task?

Until then, GitHub remains the primary project platform, and the goal is to avoid *depending* on it.  The most important thing is to avoid lock-in, so that a future break-out is cheap and easy.

## What depends on GitHub today

| What | Where it lives now | Exit path |
|---|---|---|
| Git repository | GitHub, with a copy on a server of the maintainer's (not always current) | Already portable: every clone is a full copy.  Release tags are PGP-signed, so their authenticity does not depend on the host. |
| Issues | GitHub issues | Mirrored into the repository with [git-bug](https://github.com/git-bug/git-bug) (`refs/bugs/*`, 364 issues so far).  Its GitHub bridge currently fails to import (`Multiple matching operation found`), so the mirror is stale until that is fixed. |
| Pull requests and review comments | GitHub | Not mirrored.  The commits themselves carry the reasoning (commit messages, recorded prompts), so what would be lost is the discussion. |
| Design discussions, roadmap, decisions | `docs/design/` in the repository | Already portable - that is what this directory is for. |
| CI | GitHub Actions (`.github/workflows/`) | Partly portable.  The checks call `tox` (`tox -e package`, `style`, `audit`, `docs`) and `pytest`, which run anywhere.  But the integration-test servers are set up in `tests.yaml` itself, with GitHub `services:` containers and some 200 lines of inline shell, duplicating `tests/docker-test-servers/`.  And `linkcheck.yml` opens and closes GitHub issues with `gh`. |
| Releases | Built and uploaded to PyPI from the maintainer's machine; GitHub releases are a copy of the tag notes | PyPI does not depend on GitHub today.  Moving to PyPI trusted publishing ([PR 708](https://github.com/python-caldav/caldav/pull/708)) would add a dependency.  PyPI also accepts gitlab.com as a trusted publisher, but not self-hosted GitLab, Forgejo or Codeberg. |
| Documentation | Read the Docs, built from the repository | Read the Docs can build from any public git URL: natively from GitHub, GitLab and Bitbucket, and through a generic webhook (without pull-request preview builds) from anywhere else. |
| Security reports | GitHub private vulnerability reporting, or private contact through `CONTACT.md` (see `SECURITY.md`) | The private-contact route already works without GitHub. |
| Security advisories and CVE IDs | GitHub draft security advisories, with GitHub issuing the CVE (`RELEASE-HOWTO.md`) | Request CVEs from MITRE directly, and publish the advisory in the CHANGELOG and `SECURITY.md`. |
| Contributions | GitHub pull requests | `CONTRIBUTING.md` already says a GitHub account is not required: patches by e-mail or any other channel are fine. |
| Links | `https://github.com/python-caldav/caldav/issues/NNN` in the CHANGELOG, the docs, code comments, tests, `CONTRIBUTING.md`, `SECURITY.md`, the `[project.urls]` in `pyproject.toml` and the towncrier `issue_format` | These would break on a move.  An archived GitHub repository keeps them readable; git-bug keeps the content. |

## What would make a break-out cheaper

* Fix the git-bug bridge, so the issue mirror is complete and current.  That is probably an upstream git-bug bug, to be reported there.
* Find a way to keep pull-request discussions, e.g. by having git-bug or a script archive them.
* Move the integration-test server setup out of `tests.yaml` into the `start.sh` scripts under `tests/docker-test-servers/`, so CI only calls them.  In general, keep CI logic in `tox.ini` and scripts rather than in workflow YAML.
* Prefer writing decisions into `docs/design/` or commit messages over leaving them only in GitHub comments.
