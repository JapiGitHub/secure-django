# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Count http status codes
"""
from ..frameworks.wsgi import WSGIResponse
from ..rules import RuleCallback
from ..rules_actions import RecordObservationMixin


class CountHTTPCodesCB(RecordObservationMixin, RuleCallback):

    INTERRUPTIBLE = False

    def post(self, instance, args, kwargs, options):
        response = self.storage.get_current_response()
        if response is not None:
            self.record_observation("http_code", str(response.status_code), 1)

    def failing(self, instance, args, kwargs, options):
        response = self.storage.get_current_response()
        result = response or WSGIResponse("500 Internal Server Error")
        result_action = options.get("result_action")
        if result_action is not None \
                and result_action.get("status") == "override":
            result = result_action.get("new_return_value")
        if result is not None:
            self.record_observation("http_code", str(result.status_code), 1)
