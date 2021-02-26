# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Look for known crawlers user-agents
"""
from logging import getLogger

from ..frameworks.pyramid_framework import PyramidRequest, PyramidResponse
from .record_request_context import RecordRequestContext

LOGGER = getLogger(__name__)


class RecordRequestContextPyramid(RecordRequestContext):
    def pre(self, instance, args, kwargs, options):
        self._store_request(PyramidRequest(args[0]))

    def post(self, instance, args, kwargs, options):
        self.storage.store_response(PyramidResponse(options.get("result")))
        self._clear_request()
