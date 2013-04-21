# -*- encoding: utf-8 -*-
from setuptools import setup, find_packages
import sys
import os

version = '0.1.12'

if __name__ == '__main__':
    setup(
        name='caldav',
        version=version,
        description="CalDAV (RFC4791) client library",
        classifiers=["Development Status :: 4 - Beta",
                     "Intended Audience :: Developers",
                     "License :: OSI Approved :: GNU General " \
                     "Public License (GPL)",
                     "License :: OSI Approved :: Apache Software License",
                     "Operating System :: OS Independent",
                     "Programming Language :: Python",
                     "Topic :: Office/Business :: Scheduling",
                     "Topic :: Software Development :: Libraries " \
                     ":: Python Modules"],
        keywords='',
        author='Cyril Robert',
        author_email='cyril@pantherific.com',
        url='http://bitbucket.org/cyrilrbt/caldav',
        license='GPL',
        packages=find_packages(),
        include_package_data=True,
        zip_safe=False,
        install_requires=['vobject', 'lxml', 'nose', 'coverage'],
        )
