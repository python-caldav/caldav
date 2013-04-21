#!/usr/bin/env python
# -*- encoding: utf-8 -*-


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


class PropsetError(Exception):
    pass


class ReportError(Exception):
    pass


class MkcolError(Exception):
    pass


class PutError(Exception):
    pass


class DeleteError(Exception):
    pass


class NotFoundError(Exception):
    pass
