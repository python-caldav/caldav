#!/usr/bin/env python
# -*- encoding: utf-8 -*-

def glue(url, part):
    sep = "/"
    if url.endswith("/"):
        sep = ""
    return "%s%s%s" % (url, sep, part)

