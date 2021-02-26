# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Record a WSGI request and enforce the whitelist.
"""

from logging import getLogger

from ..frameworks.wsgi import WSGIRequest
from ..rules import RuleCallback
from ..rules_actions import RecordObservationMixin

LOGGER = getLogger(__name__)


class RecordRequest(RecordObservationMixin, RuleCallback):

    INTERRUPTIBLE = False

    @property
    def whitelisted(self):
        return False

    def pre(self, instance, args, kwargs, options):
        self._store_request(WSGIRequest(args[0]))

    def _store_request(self, request):
        current_request = self.storage.get_current_request()
        trace_request = self.performance_monitoring_enabled \
            and current_request is None
        # If a request is already stored, we probably want to upgrade the
        # request object from a WSGIRequest to a DjangoRequest or another
        # framework. The request trace was already started, there is no need to
        # start a new one.
        self.storage.store_request(request, trace_request=trace_request)

        runner = self.runner
        if runner is not None and hasattr(request, "is_debug") \
                and runner.settings.get_debug_flag() is None:
            # Set the debug flag on the runner if possible and not already set.
            runner.settings.set_debug_flag(request.is_debug())

        whitelist_match = self.storage.get_whitelist_match()
        if whitelist_match is not None:
            return
        if runner is not None:
            whitelist_match = runner.settings.whitelist_match(request)
            if whitelist_match is not None and runner.whitelisted_metric:
                self.record_observation("whitelisted", whitelist_match, 1)
        # Set to False if the request is not whitelisted, in order to avoid
        # further useless lookups.
        self.storage.set_whitelist_match(whitelist_match or False)
