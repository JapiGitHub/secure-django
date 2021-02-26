# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Store a Pyramid request and response in the storage.
"""
from logging import getLogger

from ..frameworks.pyramid_framework import PyramidRequest, PyramidResponse
from .record_request import RecordRequest

LOGGER = getLogger(__name__)


class RecordRequestPyramid(RecordRequest):
    def pre(self, instance, args, kwargs, options):
        self._store_request(PyramidRequest(args[0]))

    def post(self, instance, args, kwargs, options):
        self.storage.store_response(PyramidResponse(options.get("result")))
