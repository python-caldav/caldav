#!/usr/bin/env python
# -*- encoding: utf-8 -*-


import re


def fix(event):
    fixed = re.sub('COMPLETED:(\d+)\s', 'COMPLETED:\g<1>T120000Z', event)

    return fixed
