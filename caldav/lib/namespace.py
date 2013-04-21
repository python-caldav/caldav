#!/usr/bin/env python
# -*- encoding: utf-8 -*-


nsmap = {"D": "DAV:",
         "C": "urn:ietf:params:xml:ns:caldav",
        }


def ns(prefix, tag=None):
    name = "{%s}" % nsmap[prefix]
    if tag is not None:
        name = "%s%s" % (name, tag)
    return name
