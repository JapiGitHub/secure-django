# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Record request context."""

from logging import getLogger

from ..frameworks.aiohttp_framework import AioHTTPRequest, AioHTTPResponse
from .record_request_context import RecordRequestContext

LOGGER = getLogger(__name__)


class RecordRequestContextAioHTTP(RecordRequestContext):
    """Record request context."""

    def pre(self, instance, args, kwargs, options):
        self._store_request(AioHTTPRequest(args[0]))

    def post(self, instance, args, kwargs, options):
        self.storage.store_response(AioHTTPResponse(options.get("result")))
        self._clear_request()
