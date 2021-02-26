# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" WSGI Middleware
"""
import logging
import sys

from .base import BaseMiddleware

LOGGER = logging.getLogger(__name__)


class WSGIApplicationWrapper:
    """
    WSGI Wrapper injected by the middleware to wrap the WSGI application.
    The pre callbacks are called with the WSGI environ and can override it.
    The post callbacks are called after the original application without arguments.
    The failing callbacks are called when the original application has failed.
    """

    def __init__(self, middleware, app, environ, start_response, *args):
        self.middleware = middleware
        self.orig_app = app
        self.orig_start_response = start_response
        self.orig_args = args
        self.orig_write_func = None
        self.transaction = transaction = middleware.create_transaction()
        try:
            new_args = middleware.execute_pre_callbacks(transaction, (environ,))
            if new_args:
                environ = new_args[0]
            self.it = self.serve_application(environ)
        except Exception as e:
            resp = middleware.execute_failing_callbacks(transaction, e, args=(environ,))
            if resp is None:
                raise
            # override the response
            self._start_response(resp.status, list(resp.headers.items()),
                                 sys.exc_info())
            self.it = [resp.body or b""]
            self.late_post = False
        else:
            # If we don't have the original write function, start_response
            # was not called yet and will probably be called by the iterator.
            self.late_post = self.orig_write_func is None
            if not self.late_post:
                # XXX it is not possible to override the response here because
                # we can't call start_response again without an exception. It
                # is thus not possible to alter the response (without changing
                # the Content-Length header).
                middleware.execute_post_callbacks(transaction, None, args=(environ,),
                                                  record_attack=False)

        if self.it:
            self.orig_close = getattr(self.it, "close", None)
            self.orig_len = getattr(self.it, "__len__", None)
            if self.orig_len:
                self.__len__ = self.orig_len

    def _start_response(self, *args):
        self.orig_write_func = self.start_response(*args)
        return self.write

    def serve_application(self, environ):
        """
        Wrapper around the original WSGI application.
        """
        return self.orig_app(environ, self._start_response, *self.orig_args)

    def start_response(self, status, headers, *args):
        """
        Wrapper around the original WSGI start_response function.
        """
        return self.orig_start_response(status, headers, *args)

    def write(self, data):
        """
        Wrapper around the original WSGI write function returned by
        start_response.
        If you plan to hook this function, it's probably better to use iterate.
        """
        return self.orig_write_func(data)

    def iterate(self, data):
        """
        Wrapper around the iterator returned by the WSGI application.
        It is called on each entry yielded by the iterator.
        """
        return data

    def close(self):
        """
        Wrapper around the original close function on the iterator returned by
        the WSGI application.
        """
        orig_close = getattr(self, "orig_close", None)
        if orig_close is not None:
            self.orig_close()

    def __iter__(self):
        try:
            for data in self.it:
                yield self.iterate(data)
        except Exception as e:
            if not self.orig_write_func:
                # start_response was not called yet, or was called during
                # the first iteration and failed
                resp = self.middleware.execute_failing_callbacks(self.transaction, e)
                if resp is None:
                    raise
                self._start_response(resp.status, list(resp.headers.items()),
                                     sys.exc_info())
                yield resp.body or b""
        else:
            if self.late_post:
                # Late post does not have access to the environ as it might have
                # been freed already
                self.middleware.execute_post_callbacks(self.transaction, None, record_attack=False)
        finally:
            self.close()


class WSGIMiddleware(BaseMiddleware):

    def wrap_app(self, *args):
        return WSGIApplicationWrapper(self, *args)
