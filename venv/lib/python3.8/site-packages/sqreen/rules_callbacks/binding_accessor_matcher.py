# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Abstract callback for checking regex against request fields
"""

from logging import getLogger

from ..binding_accessor import BindingAccessor
from ..exceptions import InvalidArgument
from ..matcher import Matcher
from ..performance_metrics import Trace
from ..rules import RuleCallback
from ..rules_actions import RecordAttackMixin
from ..utils import Mapping, is_string

LOGGER = getLogger(__name__)


class BindingAccessorMatcherCallback(RecordAttackMixin, RuleCallback):

    SUPPORT_BUDGETS = True
    MAX_LEN = 1024 * 128

    def __init__(self, *args, **kwargs):
        super(BindingAccessorMatcherCallback, self).__init__(*args, **kwargs)

        if not isinstance(self.data, Mapping):
            msg = "Invalid data type received: {}"
            raise InvalidArgument(msg.format(type(self.data)))

        try:
            self.values = self.data["values"]
        except KeyError:
            msg = "No key 'values' in data (had {})"
            raise InvalidArgument(msg.format(self.data.keys()))

        self.patterns = None

    def _prepare_patterns(self):
        """ Prepare patterns if not ready
        """
        patterns = []

        ba_cache = {}

        def cached_binding_accessor(expression):
            if expression in ba_cache:
                return ba_cache[expression]
            else:
                binding_accessor = BindingAccessor(expression)
                ba_cache[expression] = binding_accessor
                return binding_accessor

        try:
            for value in self.values:

                bindings = [
                    cached_binding_accessor(ba)
                    for ba in value["binding_accessor"]
                ]

                patterns.append(
                    {
                        "id": value["id"],
                        "binding_accessor": bindings,
                        "matcher": Matcher([value["matcher"]]),
                    }
                )
        finally:
            self.patterns = patterns

    def pre(self, instance, args, kwargs, options):
        request = self.storage.get_current_request()
        response = self.storage.get_current_response()

        if not request:
            LOGGER.warning("No request was recorded abort")
            return

        # Only compile patterns if we need them
        if self.patterns is None:
            self._prepare_patterns()

        budget = self.get_remaining_budget(options)

        binding_eval_args = {
            "request": request,
            "response": response,
            "inst": instance,
            "args": self.storage.get_current_args(args),
            "kwargs": kwargs,
            "data": self.data,
        }

        cache = {}
        total_pattern_time = 0
        for pattern in self.patterns:
            with Trace() as pattern_trace:
                for binding_accessor in pattern["binding_accessor"]:
                    expression = binding_accessor.expression

                    if expression in cache:
                        data = cache[expression]
                    else:
                        data = binding_accessor.resolve(**binding_eval_args)

                        # Convert string to list
                        if data is None or is_string(data):
                            data = [data]

                        # Ignore not string values as we use a string matcher
                        # that only match strings
                        data = [elem for elem in data if is_string(elem)]

                        cache[expression] = data

                    if not data:
                        continue

                    for elem in data:
                        if len(elem) > self.MAX_LEN:
                            continue

                        if pattern["matcher"].match(elem):
                            infos = {
                                "id": pattern["id"],
                                "binding_accessor": expression,
                                "matcher": pattern["matcher"].patterns,
                                "found": elem,
                            }
                            self.record_attack(infos)

                            # Potentially raise an attack
                            return {
                                "status": "raise",
                                "data": elem,
                                "rule_name": self.rule_name,
                            }
            total_pattern_time += pattern_trace.duration_ms
            if budget is not None and total_pattern_time >= budget:
                break
