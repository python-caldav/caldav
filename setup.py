#!/usr/bin/python
# -*- encoding: utf-8 -*-
from setuptools import setup, find_packages
import sys

## ATTENTION! when doing releases, the default debugmode in lib/error.py should be set to PRODUCTION.
## (TODO: any nicer ways than doing this manually?  Make a "releases" branch, maybe?)
version = '0.9.1'

if __name__ == '__main__':
    ## For python 2.7 and 3.5 we depend on pytz and tzlocal.  For 3.6 and up, batteries are included.  Same with mock. (But unfortunately the icalendar library only support pytz timezones, so we'll keep pytz around for a bit longer).
    try:
        import datetime
        from datetime import timezone
        datetime.datetime.now().astimezone(timezone.utc)
        extra_packages = []
        ## line below can be removed when https://github.com/collective/icalendar/issues/333 is fixed
        extra_packages = ['pytz', 'tzlocal']
    except:
        extra_packages = ['pytz', 'tzlocal']
    try:
        from unittest.mock import MagicMock
        extra_test_packages = []
    except:
        extra_test_packages = ['mock']

    setup(
        name='caldav',
        version=version,
        py_modules=["caldav",],
        description="CalDAV (RFC4791) client library",
        long_description=open("README.md").read(),
        classifiers=["Development Status :: 4 - Beta",
                     "Intended Audience :: Developers",
                     "License :: OSI Approved :: GNU General "
                     "Public License (GPL)",
                     "License :: OSI Approved :: Apache Software License",
                     "Operating System :: OS Independent",
                     "Programming Language :: Python",
                     "Topic :: Office/Business :: Scheduling",
                     "Topic :: Software Development :: Libraries "
                     ":: Python Modules"],
        keywords='',
        author='Cyril Robert',
        author_email='cyril@hippie.io',
        url='https://github.com/python-caldav/caldav',
        license='GPL',
        packages=find_packages(exclude=['tests']),
        include_package_data=True,
        zip_safe=False,
        install_requires=['vobject', 'lxml', 'requests', 'six'] + extra_packages,
        tests_require=['icalendar', 'nose', 'coverage', 'tzlocal', 'pytz', 'xandikos<0.2.4', 'radicale'] + extra_test_packages
    )
