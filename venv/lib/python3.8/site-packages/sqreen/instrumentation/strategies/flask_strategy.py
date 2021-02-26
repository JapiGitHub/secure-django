# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Flask hook strategy
"""

from logging import getLogger

from ..middlewares.flask_middleware import FlaskMiddleware
from .framework import FrameworkStrategy

LOGGER = getLogger(__name__)


def replace_wsgi_app(original, middleware):
    return middleware(original)


class FlaskStrategy(FrameworkStrategy):
    """ Strategy for Flask peripheric callbacks.

    It injects functions that calls pre and post callbacks in the Flask
    request workflow
    """

    MODULE_NAME = "flask.app"
    HOOK_CLASS = "Flask"
    HOOK_METHOD = "full_dispatch_request"

    def __init__(self, *args, **kwargs):
        super(FlaskStrategy, self).__init__(*args, **kwargs)

        self.middleware = FlaskMiddleware(self)
        self.wrapper = replace_wsgi_app

    @classmethod
    def get_early_strategy_id(cls):
        return None
