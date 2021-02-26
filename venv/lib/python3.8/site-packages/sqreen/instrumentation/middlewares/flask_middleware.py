# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
import sys

from ..._vendors.wrapt import FunctionWrapper
from .base import BaseMiddleware


class FlaskMiddleware(BaseMiddleware):
    def __call__(self, original):

        def wrapper(wrapped, instance, args, kwargs):
            """ Call the lifecycles methods with these arguments:
            Flask pre callbacks will receive these arguments:
            (None)
            Flask post callbacks will receive these arguments:
            (None, response)
            Flask failing callbacks will receive these arguments:
            (None, exception)
            """
            self.strategy.before_hook_point()
            transaction = self.create_transaction()

            self.execute_pre_callbacks(transaction, (), record_attack=True)

            try:
                response = wrapped(*args, **kwargs)
            except Exception:
                self.execute_failing_callbacks(transaction, sys.exc_info())
                raise
            return self.execute_post_callbacks(
                transaction, response, record_attack=True
            )

        return FunctionWrapper(original, wrapper)
