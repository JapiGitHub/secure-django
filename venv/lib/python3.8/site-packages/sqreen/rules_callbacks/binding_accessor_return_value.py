# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Use the binding accessors as a callback return value.
"""

from logging import getLogger

from ..binding_accessor import BindingAccessor
from ..rules import RuleCallback
from ..rules_actions import (
    RecordAttackMixin,
    RecordObservationMixin,
    RecordSignalMixin,
    RequestStoreMixin,
)
from ..utils import Iterable, Mapping, create_bound_method, is_string

LOGGER = getLogger(__name__)


def prepare_binding_accessors(value):
    """ Replace string values with binding accessors.
    """
    if is_string(value):
        return BindingAccessor(value)
    elif isinstance(value, Mapping):
        result = {}
        for name, exp in value.items():
            result[name] = prepare_binding_accessors(exp)
        return result
    elif isinstance(value, Iterable):
        return [prepare_binding_accessors(item) for item in value]
    return value


def resolve_binding_accessors(value, context):
    """ Resolve binding accessors.
    """
    if isinstance(value, BindingAccessor):
        return value.resolve(**context)
    elif isinstance(value, Mapping):
        result = {}
        for name, exp in value.items():
            result[name] = resolve_binding_accessors(exp, context)
        return result
    elif isinstance(value, Iterable):
        return [resolve_binding_accessors(item, context) for item in value]
    return value


class BindingAccessorReturnValue(RecordAttackMixin, RecordObservationMixin, RecordSignalMixin, RequestStoreMixin, RuleCallback):

    def __init__(self, *args, **kwargs):
        # Create callback methods dynamically according to data binding accessors
        return_values = kwargs.get("data", {}).get("values", [])
        all_bas = {}
        for lifecycle, retval in return_values:
            if lifecycle in ("pre", "post", "failing",):
                lifecycle_bas = prepare_binding_accessors(retval)
                all_bas[lifecycle] = lifecycle_bas
                self.create_callback(lifecycle)
        self.binding_accessors = all_bas

        super(BindingAccessorReturnValue, self).__init__(*args, **kwargs)

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

        binding_eval_args = {
            "request": self.storage.get_current_request(),
            "response": self.storage.get_current_response(),
            "inst": instance,
            "args": self.storage.get_current_args(args),
            "kwargs": kwargs,
            "data": self.data,
            "rv": options.get("result"),
            "request_store": self.storage.get_request_store(),
        }

        ret = resolve_binding_accessors(bas, binding_eval_args)
        LOGGER.debug("Return value is %r", ret)
        return ret
