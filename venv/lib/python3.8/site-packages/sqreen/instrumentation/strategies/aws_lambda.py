# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
import logging
import os
import sys

from ..._vendors.wrapt import FunctionWrapper
from ..middlewares.aws_lambda_middleware import AWSLambdaMiddleware
from .framework import FrameworkStrategy

LOGGER = logging.getLogger(__name__)


def wrap_handle_event_request_pre_37(original, middleware):
    def _extract(request_handler, *args, **kwargs):
        return request_handler, args, kwargs

    def wrapper(wrapped, instance, args, kwargs):
        request_handler, _args, _kwargs = _extract(*args, **kwargs)
        request_handler = middleware(request_handler)
        return wrapped(request_handler, *_args, **_kwargs)

    return FunctionWrapper(original, wrapper)


def wrap_handle_event_request(original, middleware):
    def _extract(lambda_runtime_client, request_handler, *args, **kwargs):
        return lambda_runtime_client, request_handler, args, kwargs

    def wrapper(wrapped, instance, args, kwargs):
        lambda_runtime_client, request_handler, _args, _kwargs = _extract(*args, **kwargs)
        request_handler = middleware(request_handler)
        return wrapped(lambda_runtime_client, request_handler, *_args, **_kwargs)

    return FunctionWrapper(original, wrapper)


PRE_37 = sys.version_info < (3, 7)


class AWSLambdaStrategy(FrameworkStrategy):

    MODULE_NAME = "__main__" if sys.version_info[:2] != (3, 7) else "bootstrap"
    HOOK_CLASS = None
    HOOK_METHOD = "handle_event_request"

    def __init__(self, *args, **kwargs):
        super(AWSLambdaStrategy, self).__init__(*args, **kwargs)

        self.middleware = AWSLambdaMiddleware(self)
        if PRE_37:
            self.wrapper = wrap_handle_event_request_pre_37
        else:
            self.wrapper = wrap_handle_event_request

    @classmethod
    def get_early_strategy_id(cls):
        # Quick & dirty AWS Lambda detection, we cannot use runner_thread.is_serverless due to circular import.
        if "LAMBDA_TASK_ROOT" in os.environ:
            return (
                "{}::{}".format(cls.MODULE_NAME, cls.HOOK_CLASS),
                cls.HOOK_METHOD,
            )
        return None
