# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
from ..._vendors.wrapt import FunctionWrapper
from .base import BaseMiddleware


class AWSLambdaMiddleware(BaseMiddleware):

    def __call__(self, original):
        return FunctionWrapper(original, self.wrapper)

    def wrapper(self, wrapped, instance, args, kwargs):
        def _extract(event, context, *args, **kwargs):
            return event, context
        transaction = self.create_transaction()
        self.execute_pre_callbacks(transaction, _extract(*args, **kwargs))
        try:
            ret = wrapped(*args, **kwargs)
        except Exception as e:
            ret = self.execute_failing_callbacks(transaction, e)
            if ret:
                return ret
            raise
        else:
            return self.execute_post_callbacks(transaction, ret)
