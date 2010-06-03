# -*- encoding: utf-8 -*-
from setuptools import setup, find_packages
import sys, os

version = '0.0.1'

if __name__ == '__main__':
    setup(
        name='caldav',
        version=version,
        description="CalDAV client",
        classifiers=[],
        keywords='',
        author='Cyril Robert',
        author_email='cyril.robert@auf.org',
        url='',
        license='GPL',
        packages = find_packages (),
        include_package_data=True,
        zip_safe=False,
        install_requires=['vobject', 'lxml', 'nose', 'coverage'],
        )
