# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Count HTTP codes for the aiohttp framework."""

import logging

from ..rules import RuleCallback
from ..rules_actions import RecordObservationMixin

LOGGER = logging.getLogger(__name__)


class CountHTTPCodesCBAioHTTP(RecordObservationMixin, RuleCallback):

    INTERRUPTIBLE = False

    def post(self, instance, args, kwargs, options):
        """Recover the status code and update the http_code metric."""
        response = options.get("result")
        status_code = response.status
        self.record_observation("http_code", str(status_code), 1)
        return {}

    def failing(self, instance, args, kwargs, options):
        """Recover the status code and update the http_code metric."""
        self.record_observation("http_code", "500", 1)
        return {}
