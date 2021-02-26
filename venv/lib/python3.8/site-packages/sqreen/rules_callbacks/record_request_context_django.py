# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Store a Django request and response in the storage and clear the request
context.
"""
from logging import getLogger

from ..frameworks.django_framework import DjangoRequest, DjangoResponse
from .record_request_context import RecordRequestContext

LOGGER = getLogger(__name__)


class RecordRequestContextDjango(RecordRequestContext):

    def pre(self, instance, args, kwargs, options):
        self._store_request(DjangoRequest(args[0]))

    def post(self, instance, args, kwargs, options):
        self.storage.store_response(DjangoResponse(options.get("result")))
        self._clear_request()

    def failing(self, instance, args, kwargs, options):
        """ Post is always called in a Django Middleware, don't clean the
        request right now as it may be needed in a post callback
        """
        pass
