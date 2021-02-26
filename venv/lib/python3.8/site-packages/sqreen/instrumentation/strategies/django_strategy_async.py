# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Django hook async strategy
"""
import logging

from ..._vendors.wrapt import FunctionWrapper

LOGGER = logging.getLogger(__name__)


def insert_middleware_v2(original, middleware):

    def wrapper(wrapped, instance, args, kwargs):
        LOGGER.debug("Insert new-style Django middleware")

        res = wrapped(*args, **kwargs)

        def _extract(is_async=False):
            return is_async

        # Retrieve the original middleware chain.
        orig_mw_chain = instance._middleware_chain

        # New middleware chain, including Sqreen. This function processes
        # responses, so Sqreen middleware is the last one.
        is_async = _extract(*args, **kwargs)
        if is_async:
            process_view = instance.adapt_method_mode(is_async, middleware.process_view)

            async def mw_chain(request):
                response = await orig_mw_chain(request)
                response = middleware.process_response(request, response)
                return response
        else:
            process_view = middleware.process_view

            def mw_chain(request):
                response = orig_mw_chain(request)
                response = middleware.process_response(request, response)
                return response

        # Insert Sqreen middleware.
        try:
            instance._view_middleware.insert(0, process_view)
            instance._exception_middleware.append(middleware.process_exception)
            instance._middleware_chain = mw_chain
        except Exception:
            LOGGER.warning(
                "Error while inserting our middleware", exc_info=True
            )
        return res

    return FunctionWrapper(original, wrapper)
