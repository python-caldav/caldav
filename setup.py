#!/usr/bin/python
# -*- encoding: utf-8 -*-
import ast
import re
import sys

from setuptools import find_packages
from setuptools import setup

## I believe it's good practice to keep the version number
## available as package.__version__

## It is defitively good practice not to have to maintain the
## version number several places.

# However, there seems to be no "best current practice" on how
## to set up version number in the setup.py file?

## I've copied the following from the icalendar library:
_version_re = re.compile(r"__version__\s+=\s+(.*)")
with open("caldav/__init__.py", "rb") as f:
    version = str(
        ast.literal_eval(_version_re.search(f.read().decode("utf-8")).group(1))
    )

if __name__ == "__main__":
    ## TODO: consider if automated testing with radicale in addition to
    ## xandikos would yield any benefits.
    test_packages = [
        "pytest",
        "pytest-coverage",
        "coverage",
        "sphinx",
        "backports.zoneinfo;python_version<'3.9'",
        "tzlocal",
        "xandikos==0.2.8;python_version<'3.9'",
        "dulwich==0.20.50;python_version<'3.9'",
        "xandikos;python_version>='3.9'",
    ]

    setup(
        name="caldav",
        version=version,
        py_modules=[
            "caldav",
        ],
        description="CalDAV (RFC4791) client library",
        long_description=open("README.md").read(),
        classifiers=[
            "Development Status :: 4 - Beta",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: GNU General " "Public License (GPL)",
            "License :: OSI Approved :: Apache Software License",
            "Operating System :: OS Independent",
            "Programming Language :: Python",
            "Topic :: Office/Business :: Scheduling",
            "Topic :: Software Development :: Libraries " ":: Python Modules",
        ],
        keywords="",
        author="Cyril Robert",
        author_email="cyril@hippie.io",
        url="https://github.com/python-caldav/caldav",
        license="GPL",
        packages=find_packages(exclude=["tests"]),
        include_package_data=True,
        zip_safe=False,
        install_requires=[
            "vobject",
            "lxml",
            "requests",
            "icalendar",
            "recurring-ical-events>=2.0.0",
            "typing_extensions",
        ],
        extras_require={
            "test": test_packages,
        },
    )
