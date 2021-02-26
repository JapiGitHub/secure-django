# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Record request context
"""

from logging import getLogger

from .record_request import RecordRequest

LOGGER = getLogger(__name__)


class RecordRequestContext(RecordRequest):

    def _clear_request(self):
        if self.runner is None:
            self.storage.clear_request(None, None)
        else:
            self.storage.clear_request(
                self.runner.queue, self.runner.observation_queue
            )

    def post(self, instance, args, kwargs, options):
        self._clear_request()

    def failing(self, instance, args, kwargs, options):
        self._clear_request()
