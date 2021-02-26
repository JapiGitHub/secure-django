# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Provide data to the reactive engine using binding accessors.
"""

from logging import getLogger

from ..binding_accessor import BindingAccessor
from ..rules import RuleCallback
from ..utils import create_bound_method

LOGGER = getLogger(__name__)


class BindingAccessorProvideData(RuleCallback):

    SUPPORTS_BUDGET = True

    def __init__(self, *args, **kwargs):
        # Create callback methods dynamically according to data binding accessors
        values = kwargs.get("data", {}).get("values", [])
        all_bas = {}
        for lifecycle, entries in values:
            if lifecycle in ("pre", "post", "failing",):
                lifecycle_bas = [(addr, BindingAccessor(ba)) for addr, ba in entries]
                all_bas[lifecycle] = lifecycle_bas
                self.create_callback(lifecycle)
        self.binding_accessors = all_bas

        super(BindingAccessorProvideData, self).__init__(*args, **kwargs)

    def create_callback(self, name):
        """ Create an execute callback alias called `name`.
        """
        def callback(self, instance, args, kwargs, options):
            return self.execute(name, instance, args, kwargs, options)

        try:
            callback.__name__ = name
            callback.__qualname__ = name
        except AttributeError:
            pass
        method = create_bound_method(callback, self)
        setattr(self, name, method)

    def execute(self, name, instance, args, kwargs, options):
        bas = self.binding_accessors.get(name)
        engine = self.runner.reactive
        if engine is None or not bas:
            return

        current_span = self.storage.get_request_store().get("current_span")
        if current_span is None:
            current_span = engine.create_span()
            self.storage.update_request_store(current_span=current_span)

        result = options.get("result")
        result_action = options.get("result_action")
        if result_action is not None \
                and result_action.get("status") == "override":
            result = result_action.get("new_return_value")

        binding_eval_args = {
            "request": self.storage.get_current_request(),
            "response": self.storage.get_current_response(),
            "inst": instance,
            "args": self.storage.get_current_args(args),
            "kwargs": kwargs,
            "data": self.data,
            "rv": result,
        }

        data = []
        subscribed_addresses = current_span.subscribed_addresses
        with self.storage.trace() as trace:
            for address, ba in bas:
                if address in subscribed_addresses:
                    res = ba.resolve(**binding_eval_args)
                    data.append((address, res))
        if data:
            budget = self.get_remaining_budget(options)
            if budget is not None:
                budget -= trace.duration_ms
            return current_span.provide_data(data, override_budget=budget)
