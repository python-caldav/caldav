#!/usr/bin/env python3
"""
Check that the version baked into the built artifacts is the tagged version.

Usage:
    python tests/tools/check_release_version.py DISTDIR [--tag v3.3.1]

Run by the ``publish`` workflow between building and uploading.  ``hatch-vcs``
derives the version from ``git describe``, which quietly produces a
``3.3.1.dev4+g1234567`` when the checkout is not exactly on the tag - a shallow
clone, a missing ``fetch-depth: 0``, a tag that ended up on the wrong commit.
Such a version is a perfectly valid PyPI upload, and once uploaded the number
is gone for good, so this refuses it before it can be published.

The version is read out of the artifacts' own metadata rather than parsed off
their file names, since a wheel file name mangles anything a version may
legally contain.  The comparison is between parsed PEP 440 versions rather than
strings: the tag ``v3.3.1.a1`` and the version ``3.3.1a1`` are the same
version, spelled differently.

Without ``--tag`` the tag is taken from ``$REF_NAME``; if ``$REF_TYPE`` says the
ref is not a tag (a ``workflow_dispatch`` rehearsal on a branch), the version is
reported but not enforced.
"""

from __future__ import annotations

import argparse
import email
import os
import sys
import tarfile
import zipfile
from pathlib import Path

from packaging.version import InvalidVersion, Version


def version_of(path: Path) -> str:
    """Read the Version field out of a wheel's METADATA or an sdist's PKG-INFO."""
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".dist-info/METADATA"))
            raw = zf.read(name)
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path) as tar:
            name = next(n for n in tar.getnames() if n.count("/") == 1 and n.endswith("/PKG-INFO"))
            member = tar.extractfile(name)
            assert member is not None
            raw = member.read()
    else:
        raise SystemExit(f"unexpected file in the dist directory: {path.name}")
    version = email.message_from_bytes(raw).get("Version")
    if not version:
        raise SystemExit(f"no Version in the metadata of {path.name}")
    return version


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("distdir", type=Path)
    parser.add_argument("--tag", default=os.environ.get("REF_NAME", ""))
    args = parser.parse_args()

    artifacts = sorted(args.distdir.iterdir())
    if not artifacts:
        raise SystemExit(f"no artifacts found in {args.distdir}")
    found = {path.name: version_of(path) for path in artifacts}
    for name, version in found.items():
        print(f"{name}: {version}")
    if len(set(found.values())) > 1:
        raise SystemExit("the artifacts disagree about the version")
    built = next(iter(found.values()))

    tag = args.tag
    if not tag or os.environ.get("REF_TYPE", "tag") != "tag":
        print("not building from a tag - the version is not enforced")
    else:
        try:
            wanted = Version(tag.removeprefix("v"))
        except InvalidVersion:
            raise SystemExit(f"tag {tag} is not a PEP 440 version") from None
        if Version(built) != wanted:
            raise SystemExit(
                f"the artifacts say {built} but the tag {tag} says {wanted}.  "
                "A dev or local version here means the build did not see the "
                "tag (shallow clone?), or the tag is not on the built commit."
            )
        print(f"✓ the artifacts match the tag {tag}")

    if github_output := os.environ.get("GITHUB_OUTPUT"):
        with open(github_output, "a") as fp:
            fp.write(f"version={built}\n")
            fp.write(f"prerelease={str(Version(built).is_prerelease).lower()}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
