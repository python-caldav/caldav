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
    ## For python 2.7 and 3.5 we depend on pytz and tzlocal.  For 3.6 and up, batteries are included.  Same with mock. (But unfortunately the icalendar library only support pytz timezones, so we'll keep pytz around for a bit longer).
    try:
        import datetime
        from datetime import timezone

        datetime.datetime.now().astimezone(timezone.utc)
        extra_packages = []
        ## line below can be removed when https://github.com/collective/icalendar/issues/333 is fixed
        extra_packages = ["pytz", "tzlocal"]
    except:
        extra_packages = ["pytz", "tzlocal"]
    try:
        from unittest.mock import MagicMock

        extra_test_packages = []
    except:
        extra_test_packages = ["mock"]

    test_packages = [
        "pytest",
        "pytest-coverage",
        "icalendar",
        "coverage",
        "tzlocal",
        "pytz",
        "xandikos",
        "radicale",
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
            "six",
            "icalendar",
            "recurring-ical-events>=2.0.0",
        ]
        + extra_packages,
        tests_require=test_packages + extra_test_packages,
        extras_require={
            "test": test_packages,
        },
    )
