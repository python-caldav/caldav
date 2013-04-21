#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import urlparse


def join(url, part):
    sep = "/"
    if url.endswith("/"):
        sep = ""
    return "%s%s%s" % (url, sep, part)


def make(url, path=None):
    u = ""

    if path is not None:
        u = urlparse.urlunparse((url.scheme, url.netloc, path, url.params,
                                 url.query, url.fragment))
    else:
        u = url.geturl()

    return u


def canonicalize(url, parent=None):
    if url.scheme:
        netloc_unauth = ('%s:%s' % (url.hostname, url.port)
                         if url.port not in (80, None)
                         else url.hostname)
        return urlparse.urlunparse((url.scheme, netloc_unauth,
                                    url.path.replace('//', '/'),
                                    url.params, url.query, url.fragment))
    else:
        return urlparse.urljoin(parent.canonical_url,
                                url.path.replace('//', '/'))
