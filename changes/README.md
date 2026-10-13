# Changelog fragments

Changes since the last release are not written into `CHANGELOG.md` directly.  Each change adds a small file - a "fragment" - to this directory instead, and at release time [towncrier](https://towncrier.readthedocs.io/) collects them into `CHANGELOG.md`.  Separate files mean that parallel pull requests no longer conflict in the CHANGELOG.

## File naming

`<issue>.<type>.md`, e.g. `740.fixed.md` for a fix of https://github.com/python-caldav/caldav/issues/740 - the URL is appended to the entry automatically.  A pull request number works too.  If two changes of the same type belong to one issue, add a counter: `740.fixed.1.md`, `740.fixed.2.md` (`towncrier create` picks one when the name is taken).

For a change without an issue, or when the entry cites its URLs inline (several issues, a pull request and an issue, an upstream bug report ...), use `+<slug>.<type>.md`, e.g. `+async-xml-parsing.fixed.md`.  Nothing is appended to such an entry.

The types, in the order they appear in the CHANGELOG:

| type         | section                 |
|--------------|-------------------------|
| `breaking`   | Breaking changes        |
| `added`      | Added                   |
| `changed`    | Changed                 |
| `deprecated` | Deprecated              |
| `removed`    | Removed                 |
| `fixed`      | Fixed                   |
| `security`   | Security                |
| `tests`      | Tests and documentation |

Use `tests` only for changes a user or packager notices (a new test option, a test dependency, docs that moved); a pull request that only adds or changes tests or docs needs no fragment.

## Content

Markdown, written as the text of one bullet point, without the leading `* `.  Describe the change as seen by a user of the library: what was wrong or missing, and what it does now.  Several paragraphs or a nested list are fine.

The rules in [CONTRIBUTING.md](../CONTRIBUTING.md) for what needs an entry are unchanged - a bug introduced and fixed between two releases needs none, so delete or edit the fragment of the change that introduced it instead.

`towncrier create 740.fixed.md --edit` creates a fragment, and `towncrier build --draft --version next` previews the next release section (`pip install towncrier`).
