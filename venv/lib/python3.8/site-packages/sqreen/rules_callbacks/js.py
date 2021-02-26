# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Base class for JS Callbacks
"""
import hashlib
import logging

from py_mini_racer.py_mini_racer import (  # type: ignore
    JSEvalException,
    JSTimeoutException,
)

from ..binding_accessor import BindingAccessor
from ..exceptions import SqreenException
from ..rules import RuleCallback
from ..rules_actions import (
    RecordAttackMixin,
    RecordObservationMixin,
    RecordSignalMixin,
    RequestStoreMixin,
)
from ..utils import (
    ALL_STRING_CLASS,
    CustomJSONEncoder,
    create_bound_method,
    to_unicode_safe,
)
from .mini_racer_pool import JSContextPool

LOGGER = logging.getLogger(__name__)


class JSException(SqreenException):
    """ Base exception raised in JSCB
    """

    def __init__(self, message, callback, arguments):
        super(JSException, self).__init__(message)
        self.callback = callback
        self.arguments = arguments

    def exception_infos(self):
        return {"cb": self.callback, "args": self.arguments}


class JSCB(RecordObservationMixin, RecordAttackMixin, RecordSignalMixin, RequestStoreMixin, RuleCallback):
    """ A callback that run a JS function as pre / post / failing through
    py_mini_racer context.
    """

    SUPPORTS_BUDGET = True

    def __init__(self, *args, **kwargs):
        # Create pre / post / failing callback methods on the instance early on
        # because RuleCallback.__init__ needs them.
        rule_callbacks = frozenset((kwargs.get("callbacks") or {}).keys())
        for callback_name in ("pre", "post", "failing",):
            if callback_name in rule_callbacks:
                self.create_callback(callback_name)

        super(JSCB, self).__init__(*args, **kwargs)

        self._loaded = False
        self.arguments = {}
        self.source = u''
        self.code_id = None

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

    def load(self):
        """ Create the binding accessors and save the js definitions
        """

        self.source = u''
        if self.callbacks:
            for callback_name, callback_args in self.callbacks.items():

                if not isinstance(callback_args, list):
                    self.source += u"{} = {}\n".format(callback_name, to_unicode_safe(callback_args))
                    self.arguments[callback_name] = []
                else:
                    self.source += u"{} = {}\n".format(callback_name, to_unicode_safe(callback_args[-1]))
                    arguments = callback_args[:-1]
                    self.arguments[callback_name] = [
                        BindingAccessor(arg) for arg in arguments
                    ]

        self.code_id = to_unicode_safe(hashlib.md5(self.source.encode('utf-8')).hexdigest())
        self._loaded = True

    def execute(self, name, instance, args, kwargs, options):
        """ Fetches a context before executing _execute
        """
        if self._loaded is False:
            self.load()

        budget_in_ms = self.get_remaining_budget(options)
        if budget_in_ms is not None and budget_in_ms <= 0:
            LOGGER.debug("Skipping execution of callback %s because budget is negative", name)
            return

        pool = JSContextPool.fetch_for_runner(self.runner)
        return pool.with_context(
            lambda ctx: self._execute(
                ctx, name, budget_in_ms or 0, self.arguments[name],
                instance, args, kwargs, options))

    def _execute(self, js_ctx, name, budget_in_ms, arguments,
                 instance, args, kwargs, options):
        """ Execute a JS callback passed in definition.
        Handle recording attack, observations and chaining.
        Protected against infinite recursion with a max number of JS calls
        set to 100.
        """
        exc_info = options.get("exc_info")
        result = options.get("result")

        if self.code_id in js_ctx.failed_code_ids:
            LOGGER.debug("Skipping execution of callback %s (code md5 %s)"
                         " due to previous failure of definition eval",
                         name, self.code_id)
            return

        if self.code_id not in js_ctx.code_ids:
            js_ctx.add_code(self.code_id, self.source)

        request = self.storage.get_current_request()
        response = self.storage.get_current_response()

        # Fallback on a blank request for binding accessor
        if request is None:
            request = self.storage.default_request_class(storage=self.storage)

        return_value = result if name == "post" else exc_info

        # Safeguard against infinite recursion
        for _ in range(100):
            binding_eval_args = {
                "binding": locals(),
                "global_binding": globals(),
                "request": request,
                "response": response,
                "inst": instance,
                "args": self.storage.get_current_args(args),
                "kwargs": kwargs,
                "data": self.data,
                "rv": return_value,
                "request_store": self.storage.get_request_store(),
                "options": options,
            }

            resolved_args = [
                arg.resolve(**binding_eval_args) for arg in arguments
            ]
            if name in self.conditions:
                resolved_args = self._restrict(name, resolved_args)

            LOGGER.debug("Resolved args %s for %s", resolved_args, arguments)

            try:
                callee = u"sqreen_data['{}']['{}']".format(self.code_id, name)
                result = js_ctx.call(
                    callee, *resolved_args,
                    encoder=CustomJSONEncoder, timeout=int(budget_in_ms)
                )
            except JSTimeoutException as err:
                LOGGER.debug("Budget exhausted while running JS callback: %s", err)
                return None
            except JSEvalException as err:
                raise JSException(err.args[0], name, resolved_args)

            LOGGER.debug("JS Result %r for %s", result, self.rule_name)

            if result is None:
                return result

            # Check for chaining
            if result.get("call") is None:
                return result

            result = self.action_processor(result, options)

            # Prepare next call
            name = result["call"]

            if name not in self.callbacks:
                raise JSException(
                    "Invalid callback '{}'".format(name), name, None
                )

            return_value = result.get("data")

            if result.get("args"):
                arguments = [BindingAccessor(arg) for arg in result["args"]]
            else:
                arguments = self.arguments[name]

    def _restrict(self, name, arguments):
        """ Filter out useless values from iterables present in *arguments*.
        It only supports conditions with a single hash_val_include.
        """
        if name not in self.conditions or name not in self.arguments:
            return arguments
        condition = self.conditions[name]
        expressions = [
            accessor.expression for accessor in self.arguments[name]
        ]
        for value, iterable, min_length in self.iter_hash_val_include_values(
            condition
        ):
            try:
                value_idx = expressions.index(value)
                iterable_idx = expressions.index(iterable)
            except ValueError:
                continue
            arguments[iterable_idx] = self.hash_value_included(
                arguments[value_idx], arguments[iterable_idx], int(min_length)
            )
        return arguments

    @classmethod
    def iter_hash_val_include_values(cls, condition):
        """ Yield arguments of operator %hash_val_includes in *condition*.
        """
        values = condition.get("%hash_val_include")
        if len(condition) == 1 and values is not None:
            yield values

    @classmethod
    def hash_value_included(cls, needed, iterable, min_length=8, max_depth=20):
        """ Return a filtered, deep copy of dict *iterable*, where only
        (sub)values included in *needed* are present.
        """
        needed = to_unicode_safe(needed)
        result = {}
        insert = []
        todos = [(result, key, value, 0) for key, value in iterable.items()]
        while todos:
            where, key, value, depth = todos.pop()
            if not isinstance(key, (int, ALL_STRING_CLASS)):
                key = str(key)
            if depth >= max_depth:
                insert.append((where, key, value))
            elif isinstance(value, dict):
                val = {}
                insert.append((where, key, val))
                todos.extend((val, k, v, depth + 1) for k, v in value.items())
            elif isinstance(value, list):
                val = []
                insert.append((where, key, val))
                todos.extend(
                    (val, k, v, depth + 1) for k, v in enumerate(value)
                )
            elif value is not None and needed is not None:
                v = to_unicode_safe(value)
                if len(v) < min_length or v not in needed:
                    pass
                elif isinstance(where, list):
                    where.append(value)
                else:
                    where[key] = value
        for where, key, value in reversed(insert):
            if not value:
                pass
            elif isinstance(where, list):
                where.append(value)
            else:
                where[key] = value
        return result
