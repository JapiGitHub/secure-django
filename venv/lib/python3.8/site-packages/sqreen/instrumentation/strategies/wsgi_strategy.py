# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" WSGI hook strategy
"""
from functools import partial

from ..._vendors.wrapt import FunctionWrapper
from ..middlewares.wsgi_middleware import WSGIMiddleware
from .import_hook import ImportHookStrategy


class WSGIStrategy(ImportHookStrategy):
    """
    Strategy to wrap a WSGI application.
    """

    def import_hook_callback(self, original):
        middleware = WSGIMiddleware(self)

        def wrapper(wrapped, instance, args, kwargs):
            return middleware.wrap_app(wrapped, *args)

        return FunctionWrapper(original, wrapper)


class WSGIReceiverStrategy(ImportHookStrategy):
    """
    Strategy to wrap a WSGI application passed as the first argument of a
    function call.
    """

    def import_hook_callback(self, original):
        middleware = WSGIMiddleware(self)

        def wrapper(wrapped, instance, args, kwargs):
            if args and callable(args[0]):
                new_args = list(args)
                new_args[0] = partial(middleware.wrap_app, args[0])
                args = new_args
            return wrapped(*args, **kwargs)

        return FunctionWrapper(original, wrapper)


class WSGIFactoryStrategy(ImportHookStrategy):
    """
    Strategy to wrap a WSGI application factory.
    """

    def import_hook_callback(self, original):
        middleware = WSGIMiddleware(self)

        def wrapper(wrapped, instance, args, kwargs):
            app = wrapped(*args, **kwargs)
            return partial(middleware.wrap_app, app)

        return FunctionWrapper(original, wrapper)
