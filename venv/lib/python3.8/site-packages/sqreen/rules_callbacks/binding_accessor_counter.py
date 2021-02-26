# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Count things according to a list of binding accessors expression
"""
import json
import logging

from ..binding_accessor import BindingAccessor
from ..exceptions import InvalidArgument
from ..frameworks.wsgi import WSGIResponse
from ..rules import RuleCallback
from ..rules_actions import RecordObservationMixin
from ..utils import Iterable

LOGGER = logging.getLogger(__name__)


class BindingAccessorCounter(RecordObservationMixin, RuleCallback):

    INTERRUPTIBLE = False

    def __init__(self, *args, **kwargs):
        super(BindingAccessorCounter, self).__init__(*args, **kwargs)

        values = self.data.get("values")
        if values is None or not isinstance(values, Iterable):
            msg = "Invalid data type received: {}"
            raise InvalidArgument(msg.format(type(self.data)))

        self.patterns = [BindingAccessor(exp) for exp in values]
        self.metric_name = self.metrics[0]["name"]

    def post(self, instance, args, kwargs, options):
        """ Resolve binding expressions with the HTTP Response and send
        an observation for the rule metric.
        """
        request = self.storage.get_current_request()
        response = self.storage.get_current_response()

        binding_eval_args = {
            "request": request,
            "response": response,
            "inst": instance,
            "args": self.storage.get_current_args(args),
            "kwargs": kwargs,
            "data": self.data,
            "rv": options.get("result"),
        }

        key = [
            binding.resolve(**binding_eval_args) for binding in self.patterns
        ]
        formatted_key = json.dumps(key, separators=(",", ":"))
        self.record_observation(self.metric_name, formatted_key, 1)

    def failing(self, instance, args, kwargs, options):
        """ Resolve binding expressions with the exception, get the status code
        from the result action and send an observation for the rule metric.
        """
        request = self.storage.get_current_request()
        response = self.storage.get_current_response()
        result = response or WSGIResponse("500 Internal Server Error")
        result_action = options.get("result_action")
        if result_action is not None \
                and result_action.get("status") == "override":
            result = result_action.get("new_return_value")

        binding_eval_args = {
            "request": request,
            "response": response,
            "inst": instance,
            "args": self.storage.get_current_args(args),
            "kwargs": kwargs,
            "data": self.data,
            "rv": result,
        }

        key = [
            binding.resolve(**binding_eval_args) for binding in self.patterns
        ]
        formatted_key = json.dumps(key, separators=(",", ":"))
        self.record_observation(self.metric_name, formatted_key, 1)
