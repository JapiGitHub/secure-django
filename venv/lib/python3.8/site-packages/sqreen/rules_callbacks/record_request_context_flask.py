# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Record the current request in flask application
"""
from logging import getLogger

from ..frameworks.flask_framework import FlaskRequest, FlaskResponse
from .record_request_context import RecordRequestContext

LOGGER = getLogger(__name__)


class RecordRequestContextFlask(RecordRequestContext):
    def pre(self, instance, args, kwargs, options):
        from flask import _request_ctx_stack

        reqctx = _request_ctx_stack.top
        if reqctx is not None:
            self._store_request(FlaskRequest(reqctx.request))

    def post(self, instance, args, kwargs, options):
        self.storage.store_response(FlaskResponse(options.get("result")))
        self._clear_request()
