# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Django hook strategy
"""

from logging import getLogger

from ..._vendors.wrapt import FunctionWrapper
from ...utils import HAS_ASYNCIO
from ..middlewares.django_middleware import DjangoMiddleware
from .framework import FrameworkStrategy

LOGGER = getLogger(__name__)

if HAS_ASYNCIO:
    from .django_strategy_async import insert_middleware_v2


def load_middleware_insert(original, middleware):
    from django import VERSION as DJANGO_VERSION

    LOGGER.debug("Detected Django version %r", DJANGO_VERSION)

    if DJANGO_VERSION[:2] >= (2, 0) and HAS_ASYNCIO:
        return insert_middleware_v2(original, middleware)

    def wrapper(wrapped, instance, args, kwargs):
        res = wrapped(*args, **kwargs)
        LOGGER.debug("Insert old-style Django middleware")
        # Insert Sqreen middleware.
        try:
            instance._view_middleware.insert(0, middleware.process_view)
            instance._response_middleware.append(middleware.process_response)
            instance._exception_middleware.append(middleware.process_exception)
        except Exception:
            LOGGER.warning(
                "Error while inserting our middleware", exc_info=True
            )
        return res

    return FunctionWrapper(original, wrapper)


class DjangoStrategy(FrameworkStrategy):
    """ Strategy for Django peripheric callbacks.

    It injects a custom DjangoFramework that calls callbacks for each
    lifecycle method
    """

    MODULE_NAME = "django.core.handlers.base"
    HOOK_CLASS = "BaseHandler"
    HOOK_METHOD = "load_middleware"

    def __init__(self, *args, **kwargs):
        super(DjangoStrategy, self).__init__(*args, **kwargs)
        self.middleware = DjangoMiddleware(self)
        self.wrapper = load_middleware_insert
