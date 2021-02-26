# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Transform HTTP headers
"""
import logging
import re
import string

from ..binding_accessor import BindingAccessor
from ..condition_evaluator import ConditionEvaluator
from ..exceptions import InvalidArgument
from ..rules import RuleCallback
from ..utils import Mapping

LOGGER = logging.getLogger(__name__)


def transformer_to_func(transformer, func=None):
    func = func or (lambda x, _: x)  # noqa: E731

    format_args = transformer.get("format")
    if format_args is not None:
        spec = format_args[0]
        arg_bas = [BindingAccessor(arg) for arg in format_args[1:]]

        def format_func(f):
            def inner(entry, callback):
                binding_eval_args = {
                    "request": callback.storage.get_current_request(),
                    "response": callback.storage.get_current_response(),
                    "inst": callback,
                    "data": callback.data,
                    "binding": entry,
                }
                args = [arg.resolve(**binding_eval_args) for arg in arg_bas]
                entry["value"] = string.Formatter().vformat(spec, args, None)
                return f(entry, callback)
            return inner

        func = format_func(func)

    condition = transformer.get("condition")
    if condition is not None:
        condition_eval = ConditionEvaluator(condition)

        def condition_func(f):
            def inner(entry, callback):
                binding_eval_args = {
                    "request": callback.storage.get_current_request(),
                    "response": callback.storage.get_current_response(),
                    "inst": callback,
                    "data": callback.data,
                    "binding": entry,
                }
                if condition_eval.evaluate(**binding_eval_args):
                    return f(entry, callback)
                return entry
            return inner

        func = condition_func(func)

    match_value = transformer.get("match_value")
    if match_value is not None:
        match_pattern = re.compile(match_value)

        def match_value_func(f):
            def inner(entry, callback):
                match = match_pattern.match(entry.get("value", ""))
                entry["match_value"] = match.groups() if match is not None else tuple()
                return f(entry, callback)
            return inner

        func = match_value_func(func)

    return func


class BaseHeadersTransform(RuleCallback):
    """ Base class for header transformation callbacks
    """

    def __init__(self, *args, **kwargs):
        super(BaseHeadersTransform, self).__init__(*args, **kwargs)

        if not isinstance(self.data, Mapping):
            msg = "Invalid data type received: {}"
            raise InvalidArgument(msg.format(type(self.data)))

        self.transformers = {}
        for transformer in self.data.get("values", []):
            for header in transformer.get("headers", []):
                func = self.transformers.get(header.lower(), None)
                self.transformers[header.lower()] = transformer_to_func(transformer, func)

    def transform_headers(self, headers):
        # Apply transformers to headers
        for name, value in headers:
            func = self.transformers.get(name.lower())
            if func is not None:
                ret = func({"name": name, "value": value}, self)
                value = ret.get("value")
                if value is not None:
                    yield name, value
            else:
                yield name, value


class HeadersTransform(BaseHeadersTransform):
    """ Callback that transform the headers in WSGI
    """

    def pre(self, instance, args, kwargs, options):
        new_args = list(args)
        current_headers = args[1]

        # Apply transformers to headers
        new_args[1] = list(self.transform_headers(current_headers))

        return {"status": "modify_args", "args": [new_args, kwargs]}
