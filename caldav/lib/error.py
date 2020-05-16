#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from collections import defaultdict


class AuthorizationError(Exception):
    """
    The client encountered an HTTP 403 error and is passing it on
    to the user. The url property will contain the url in question,
    the reason property will contain the excuse the server sent.
    """
    url = None
    reason = "PHP at work[tm]"

    def __str__(self):
        return "AuthorizationError at '%s', reason '%s'" % \
            (self.url, self.reason)


class DAVError(Exception):
    pass


class PropsetError(DAVError):
    pass

class ProppatchError(DAVError):
    pass


class PropfindError(DAVError):
    pass


class ReportError(DAVError):
    pass


class MkcolError(DAVError):
    pass


class MkcalendarError(DAVError):
    pass


class PutError(DAVError):
    pass


class DeleteError(DAVError):
    pass


class NotFoundError(DAVError):
    pass

class ConsistencyError(DAVError):
    pass

exception_by_method = defaultdict(lambda: DAVError)
for method in ('delete', 'put', 'mkcalendar', 'mkcol', 'report', 'propset',
               'propfind', 'proppatch'):
    exception_by_method[method] = \
        locals()[method[0].upper() + method[1:] + 'Error']
