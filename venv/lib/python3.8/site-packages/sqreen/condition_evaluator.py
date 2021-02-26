# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Condition evaluator."""

import operator
from collections import deque
from functools import wraps
from itertools import islice
from logging import getLogger

from .binding_accessor import BindingAccessor
from .exceptions import SqreenException
from .utils import (
    convert_to_string,
    is_unicode,
    iterkeys,
    itervalues,
    to_unicode_safe,
)

LOGGER = getLogger(__name__)


class ConditionError(SqreenException):
    """Base class for condition errors."""


class ConditionValueError(ConditionError):
    """Exception raised when the condition is invalid."""


class ConditionRecursionError(ConditionError):
    """Exception raised when the condition is too deeply nested."""


def str_included(haystack, needle, min_needle_length=0):
    """Check if a needle is contained into the haystack.

    Haystack is an object and needle is a string. This function
    will do its best to convert the needle and the haystack to a
    string and might use str() on unknown objects, in this case,
    if needle is found it returns True.
    """
    # Convert needle to unicode and check it is long enough
    needle = to_unicode_safe(needle)
    if needle is None or len(needle) < min_needle_length:
        return False

    if is_unicode(haystack):
        # Simplest case, needle and haystack are unicode, substring match
        return needle in haystack
    elif isinstance(haystack, (list, tuple)):
        # Iterate over all items, if any of the item contains needle, we return True
        # otherwise, if any of the items has an unexpected type, we try to convert it
        # to unicode and look for needle in it
        for idx, elem in enumerate(haystack):
            if is_unicode(elem):
                # Both needle and elem are unicode, substring match
                if needle in elem:
                    return True
            else:
                try:
                    if needle in convert_to_string(elem):
                        return True
                except ValueError:
                    # Best effort convertion to unicode
                    elem_safe = to_unicode_safe(elem)
                    if elem_safe is not None and needle in elem_safe:
                        return True
    else:
        try:
            if needle in convert_to_string(haystack):
                return True
        except ValueError:
            # Best effort, we check for needle in a repr of the haystack
            haystack_safe = to_unicode_safe(haystack)
            if haystack_safe is not None and needle in haystack_safe:
                return True

    return False


def hash_value_includes(value, iterable, min_value_size, max_iterations=1000):
    """Check whether a nested iterable is included into value object.

    The iterable can be a combination of dicts and lists. The argument
    min_value_size  is used to avoid comparison on small strings: For example,
    there is no possible SQL injection below 8 characters.
    """
    # Early stop.
    if iterable is None or value is None:
        return False

    iteration = 0
    remaining_iterables = deque([iterable], maxlen=max_iterations)
    while remaining_iterables:

        iteration += 1
        # If we have a very big or nested iterable, return True to execute the
        # rule.
        if iteration >= max_iterations:
            return True

        iterable = remaining_iterables.popleft()
        # If we get an iterable, add it to the list of remaining iterables.
        if isinstance(iterable, dict):
            remaining_iterables.extend(islice(itervalues(iterable), max_iterations))
        elif isinstance(iterable, (list, tuple)):
            remaining_iterables.extend(islice(iter(iterable), max_iterations))
        elif str_included(value, iterable, min_value_size):
            return True

    return False


def hash_key_includes(patterns, iterable, min_value_size, max_iterations=1000):
    """Check whether a nested iterable key matches a pattern or a list of patterns.

    The iterable can be a combination of dicts and lists. The argument
    min_value_size is used to avoid comparison on small strings: for example,
    there is no possible MongoDB injection below 1 characters.
    """
    # Early stop.
    if iterable is None or patterns is None:
        return False

    iteration = 0
    keys = deque(maxlen=max_iterations)
    remaining_iterables = deque([iterable], maxlen=max_iterations)
    while remaining_iterables:

        while keys:
            if str_included(patterns, keys.popleft(), min_value_size):
                return True

        iteration += 1
        # If we have a very big or nested iterable, return True to execute the
        # rule.
        if iteration >= max_iterations:
            return True

        iterable = remaining_iterables.popleft()
        # If we get an iterable, add it to the list of remaining iterables.
        if isinstance(iterable, dict):
            # We have new keys to test, remaining_iterables won't be empty
            keys.extend(islice(iterkeys(iterable), max_iterations))
            remaining_iterables.extend(islice(itervalues(iterable), max_iterations))
        elif isinstance(iterable, (list, tuple)):
            remaining_iterables.extend(islice(iter(iterable), max_iterations))

    return False


def unpack_parameters(f):
    """Unpack first argument into multiple arguments."""
    @wraps(f)
    def wrapper(values, **kwargs):
        return f(*values, **kwargs)
    return wrapper


def coerce_operator_types(operator):
    """Convert operator arguments when they are incompatibles.

    The items can be either integers, strings, bytes, list of items and dict of
    items. In order to avoid complexity, only the first level of items are
    converted. Operators are responsible to convert nested items.
    """
    @wraps(operator)
    def wrapper(*args, **kwargs):
        arg_types = [type(arg) for arg in args]
        # do nothing if all types are the same
        if arg_types and arg_types.count(arg_types[0]) != len(arg_types):
            # otherwise, convert the types to unicode whenever possible
            nargs = []
            for arg in args:
                if isinstance(arg, bytes):
                    arg = arg.decode('utf-8', errors='replace')
                elif isinstance(arg, (list, tuple)):
                    arg = [
                        (v.decode('utf-8', errors='replace') if isinstance(v, bytes) else v)
                        for v in arg
                    ]
                elif isinstance(arg, dict):
                    # Convert the key only (values are not used by basic operators like %include)
                    arg = {
                        (k.decode('utf-8', errors='replace') if isinstance(k, bytes) else k): v
                        for k, v in arg.items()
                    }
                nargs.append(arg)
            args = nargs
        return operator(*args, **kwargs)
    return wrapper


OPERATORS = {
    "%and": all,
    "%or": any,
    "%equals": unpack_parameters(coerce_operator_types(operator.eq)),
    "%not_equals": unpack_parameters(coerce_operator_types(operator.ne)),
    "%gt": unpack_parameters(coerce_operator_types(operator.gt)),
    "%gte": unpack_parameters(coerce_operator_types(operator.ge)),
    "%lt": unpack_parameters(coerce_operator_types(operator.lt)),
    "%lte": unpack_parameters(coerce_operator_types(operator.le)),
    "%include": unpack_parameters(coerce_operator_types(operator.contains)),
    "%hash_val_include": unpack_parameters(coerce_operator_types(hash_value_includes)),
    "%hash_key_include": unpack_parameters(coerce_operator_types(hash_key_includes)),
}

OPERATORS_ARITY = {
    "%equals": 2,
    "%not_equals": 2,
    "%gt": 2,
    "%gte": 2,
    "%lt": 2,
    "%lte": 2,
    "%include": 2,
    "%hash_val_include": 3,
    "%hash_key_include": 3,
}


def is_condition_empty(condition):
    """Return True if the condition is no-op, False otherwise."""
    if condition is None:
        return True
    elif isinstance(condition, bool):
        return False
    elif isinstance(condition, dict):
        return len(condition) == 0
    else:
        LOGGER.warning("Invalid precondition type: %r", condition)
        return True


def compile_condition(condition, level):
    """Compile a raw condition and validate it.

    Values are replaced by BindingAccessor instances and operator validity and
    arity are checked.
    """
    if level <= 0:
        raise ConditionRecursionError("compile recursion depth exceeded")

    if isinstance(condition, bool):
        return condition

    if not isinstance(condition, dict):
        raise ConditionValueError(
            "condition should be a dict, got {}".format(type(condition))
        )

    compiled = {}

    for _operator, values in condition.items():

        # Check operator validity.
        if _operator not in OPERATORS:
            raise ConditionValueError("unkown operator {!r}".format(_operator))

        # Check operator arity.
        arity = OPERATORS_ARITY.get(_operator, len(values))
        if len(values) != arity:
            raise ConditionValueError(
                "bad arity for operator {!r}: expected {}, got {}".format(
                    _operator, arity, len(values)
                )
            )

        # Check types.
        if not isinstance(values, list):
            raise ConditionValueError(
                "values should be an array, got {}".format(type(values))
            )

        compiled_values = []
        for value in values:
            if isinstance(value, bool):
                compiled_values.append(value)
            elif isinstance(value, dict):
                compiled_values.append(compile_condition(value, level - 1))
            else:
                # XXX we should warn on this because not all types will nicely convert to string
                # and most of the time it will repr() the value.
                compiled_values.append(BindingAccessor(to_unicode_safe(value)))

        compiled[_operator] = compiled_values

    return compiled


def evaluate(value, level=1, **kwargs):
    """Evaluate a value."""

    if isinstance(value, BindingAccessor):
        return value.resolve(**kwargs)

    elif isinstance(value, dict):

        if level <= 0:
            raise ConditionRecursionError("resolve recursion depth exceeded")

        for operator_name, values in value.items():
            operator_func = OPERATORS.get(operator_name)
            if operator_func is None:
                raise ConditionValueError("unkown operator {!r}".format(operator_name))

            # Create a lazily evaluated value generator
            values = (evaluate(v, level - 1, **kwargs) for v in values)
            result = operator_func(values)
            if result is False:
                return False

        return True

    return value


class ConditionEvaluator(object):
    """Evaluate a condition, resolving literals using BindingAccessor.

    {"%and": ["true", "true"]} -> true
    {"%or": ["true", "false"]} -> true
    {"%and": ["false", "true"]} -> false
    {"%equal": ["coucou", "#.args[0]"]} -> "coucou" == args[0]
    {"%hash_val_include": ["toto is a small guy", "#.request_params", 0]} ->
        true if one value of request params in included
        in the sentence 'toto is a small guy'.

    Combined expressions:
    { "%or":
        [
            {"%hash_val_include": ["AAA", "#.request_params", 0]},
            {"%hash_val_include": ["BBB", "#.request_params", 0]},
        ]
    }
    will return true if one of the request_params includes either AAA or BBB.
    """

    def __init__(self, condition):
        self.raw_condition = condition
        self.compiled = compile_condition(condition, 10)

    def evaluate(self, **kwargs):
        """Evaluate the compiled condition and return the result."""
        return evaluate(self.compiled, 10, **kwargs)

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self.raw_condition)
