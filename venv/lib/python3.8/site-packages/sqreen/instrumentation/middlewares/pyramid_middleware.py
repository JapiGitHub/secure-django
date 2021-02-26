# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
import sys

from ..._vendors.wrapt import FunctionWrapper
from .base import BaseMiddleware


class PyramidMiddleware(BaseMiddleware):

    def __call__(self, original):

        def wrapper(wrapped, instance, args, kwargs):
            """ Call the lifecycles methods with these arguments:
            Pyramid pre callbacks will receive these arguments:
            (None, request)
            Pyramid post callbacks will receive these arguments:
            (None, response)
            Pyramid failing callbacks will receive these arguments:
            (None, exception)
            """
            from pyramid.response import Response  # type: ignore

            request = args[0]
            self.strategy.before_hook_point()
            transaction = self.create_transaction()
            pre_args = (request,)
            self.execute_pre_callbacks(transaction, pre_args, record_attack=True)

            try:
                response = wrapped(*args, **kwargs)
            except Exception as e:
                if isinstance(e, Response):
                    self.execute_post_callbacks(transaction, e)
                else:
                    self.execute_failing_callbacks(transaction, sys.exc_info())
                raise

            return self.execute_post_callbacks(
                transaction, response, record_attack=True
            )

        return FunctionWrapper(original, wrapper)
