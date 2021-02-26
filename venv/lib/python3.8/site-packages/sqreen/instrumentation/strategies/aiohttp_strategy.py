# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Strategy classes for aiohttp."""

from logging import getLogger

from ..._vendors.wrapt import FunctionWrapper
from .framework import FrameworkStrategy
from .import_hook import ImportHookStrategy

LOGGER = getLogger(__name__)


def get_aiohttp_middleware():
    """Return the aiohttp middleware to be installed.

    In aiohttp 2.2, middlewares are factory functions that return request
    handlers. In aiohttp 2.3, middleware factories (aka old-style middlewares)
    are deprecated in favor of simpler middleware functions, decorated with
    aiohttp.web.middleware. This function returns a suited middleware,
    depending on aiohttp version.
    """
    from ..middlewares.aiohttp_middleware import AioHTTPMiddleware

    try:
        from aiohttp import web
    except ImportError:
        LOGGER.debug("Cannot import aiohttp.web", exc_info=True)
        web = None
    if hasattr(web, "middleware"):
        LOGGER.debug("New style middlewares are supported")
        return AioHTTPMiddleware.handle
    LOGGER.debug("New style middlewares are not supported")
    return AioHTTPMiddleware.factory


class AioHTTPInstallStrategy(ImportHookStrategy):
    """Wrap aiohttp.web::Application.freeze to install a custom middleware."""

    def import_hook_callback(self, original):
        def wrapper(wrapped, instance, args, kwargs):
            middleware = get_aiohttp_middleware()
            if middleware in instance._middlewares:
                # Prevents inserting the middleware twice.
                LOGGER.warning("Custom middleware already set, skipped")
            else:
                LOGGER.info("Injecting custom middleware")
                instance._middlewares.insert(0, middleware)
            return wrapped(*args, **kwargs)

        return FunctionWrapper(original, wrapper)


class AioHTTPHookStrategy(FrameworkStrategy):
    """Hook aiohttp custom middleware."""

    MODULE_NAME = "sqreen.instrumentation.middlewares.aiohttp_middleware"
    HOOK_CLASS = "AioHTTPMiddleware"
    HOOK_METHOD = "handle"

    def __init__(self, *args, **kwargs):
        from ..middlewares.aiohttp_middleware import AioHTTPMiddleware

        super(AioHTTPHookStrategy, self).__init__(*args, **kwargs)
        self.middleware = AioHTTPMiddleware(self)

    @classmethod
    def get_early_strategy_id(cls):
        return None
