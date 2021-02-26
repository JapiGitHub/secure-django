# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Pyramid hook strategy
"""

from logging import getLogger

from ..middlewares.pyramid_middleware import PyramidMiddleware
from .framework import FrameworkStrategy

LOGGER = getLogger(__name__)


def tween_call_insert(original, middleware):
    def wrapped_tween_call(self, handler, *args, **kwargs):
        LOGGER.debug("Execute tween_call_insert")
        new_handler = middleware(handler)

        return original(self, new_handler, *args, **kwargs)

    return wrapped_tween_call


class PyramidStrategy(FrameworkStrategy):
    """ Strategy for Pyramid peripheric callbacks.

    It injects a custom PyramidMiddleware that calls callbacks for each
    lifecycle method
    """

    MODULE_NAME = "pyramid.config.tweens"
    HOOK_CLASS = "Tweens"
    HOOK_METHOD = "__call__"

    def __init__(self, *args, **kwargs):
        super(PyramidStrategy, self).__init__(*args, **kwargs)
        self.middleware = PyramidMiddleware(self)
        self.wrapper = tween_call_insert

    @classmethod
    def get_early_strategy_id(cls):
        return None
