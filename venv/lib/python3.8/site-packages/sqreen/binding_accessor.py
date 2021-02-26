# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Binding accessor class."""

import collections
import re
import sys
import types

from ._vendors.urllib3.packages.six import reraise  # type: ignore
from .utils import HAS_TYPING, Mapping, flatten, is_string

if HAS_TYPING:
    from typing import (
        Any,
        Callable,
        Dict,
        Iterable,
        List,
        Match,
        Optional,
        Pattern,
        Sequence,
        Tuple,
        Union,
    )

    ExcType = Tuple[type, BaseException, types.TracebackType]


def transform_int(value, exc=None, params=[], **kwargs):
    # type: (Any, Optional[ExcType], Sequence[BindingAccessorPart], **Any) -> Any
    """Return an integer."""
    if exc:
        reraise(*exc)
    base = params[0].resolve(**kwargs) if params else 10
    return int(value, base)


def transform_len(value, exc=None, params=[], **kwargs):
    # type: (Any, Optional[ExcType], Sequence[BindingAccessorPart], **Any) -> Any
    """Return the length of the iterable."""
    if exc:
        reraise(*exc)
    return len(value)


def flat_keys(value, exc=None, params=[], **kwargs):
    # type: (Any, Optional[ExcType], Sequence[BindingAccessorPart], **Any) -> Any
    """Return the length of the iterable."""
    """Return the list of keys in iterable and nested iterables."""
    if exc:
        reraise(*exc)
    max_iterations = params[0].resolve(**kwargs) if params else 1000
    keys, _ = flatten(value, max_iterations=max_iterations)
    return keys


def flat_values(value, exc=None, params=[], **kwargs):
    # type: (Any, Optional[ExcType], Sequence[BindingAccessorPart], **Any) -> Any
    """Return the list of values in iterable and nested iterables."""
    if exc:
        reraise(*exc)
    max_iterations = params[0].resolve(**kwargs) if params else 1000
    _, values = flatten(value, max_iterations=max_iterations)
    return values


def transform_default(value, exc=None, params=[], **kwargs):
    # type: (Any, Optional[ExcType], Sequence[BindingAccessorPart], **Any) -> Any
    """Resolve the parameter if the previous binding accessor resolution
    or transformation raised an exception else return the value as it is.
    """
    if exc:
        if params:
            return params[0].resolve(**kwargs)
        return None
    return value


def transform_type(value, exc=None, params=[], **kwargs):
    # type: (Any, Optional[ExcType], Sequence[BindingAccessorPart], **Any) -> Any
    """Get the type of a binding accessor resolved value.
    """
    if exc:
        reraise(*exc)
    return type(value).__name__


def transform_encode(value, exc=None, params=[], **kwargs):
    # type: (Any, Optional[ExcType], Sequence[BindingAccessorPart], **Any) -> Any
    """Transform to encode a value to bytes.
    """
    if exc:
        reraise(*exc)
    if isinstance(value, bytes):
        return value
    encoding = "utf-8"
    errors = "replace"
    if params:
        encoding = params[0].resolve(**kwargs)
        if len(params) > 1:
            errors = params[1].resolve(**kwargs)
    if not is_string(value):
        value = str(value)
    return value.encode(encoding=encoding, errors=errors)


def transform_pick(value, exc=None, params=[], **kwargs):
    """Transform to get a subset of a dict.
    """
    if exc:
        reraise(*exc)
    params = [item.resolve(**kwargs) for item in params]
    if isinstance(value, Mapping):
        return {name: value.get(name) for name in params}
    return {name: None for name in params}


class StringScanner(object):
    """Lexical scanning operations on a string.

    This is a poor man equivalent of Ruby's StringScanner class.
    """

    __slots__ = ("string", "_size", "_pos", "match")

    def __init__(self, string):  # type: (str) -> None
        self.string = string
        self._size = len(string)
        self._pos = 0
        self.match = None  # type: Optional[Match[str]]

    def tell(self):  # type: () -> int
        """Return the current position in the string."""
        return self._pos

    def rewind(self, delta):  # type: (int) -> None
        """Move the cursor back `delta` characters.
        """
        self._pos -= delta

    def scan_string(self, sub):  # type: (str) -> Optional[str]
        """Find the given substring from the current position.

        If the substring is present, the cursor position is updated and the
        substring is returned. Otherwise, this method returns None.

        This is semantically equivalent to calling scan_regex with an exact
        regexp, but faster.
        """
        size = len(sub)
        if self.string[self._pos : self._pos + size] == sub:
            self._pos += size
            return sub
        return None

    def scan_regex(self, regex):
        # type: (Pattern[str]) -> Optional[Match[str]]
        """Match the regex from the current position.

        If there is a match, the cursor position is updated and the match
        object is returned. Otherwise, this method returns None.
        """
        self.match = regex.match(self.string, self._pos)
        if self.match is not None:
            self._pos += len(self.match.group(0))
            return self.match
        return None

    def scan_until(self, delimiter=None):
        # type: (Optional[str]) -> Iterable[None]
        """Helper for common scan until a delimiter pattern.

        Yield until the delimiter or the end of the string is reached.
        The generator also stops when the scanner does not advance the scanner.
        """
        pos = self.tell()
        while not self.finished() and not (delimiter and self.scan_string(delimiter)):
            yield
            if pos == self.tell():
                raise ValueError("parsing error, scanner is stuck")

    def scan_until_regex(self, regex):
        # type: (Pattern[str]) -> Iterable[None]
        """Same helper than scan_until but using a regular expression.
        """
        pos = self.tell()
        while not self.finished() and not self.scan_regex(regex):
            yield
            if pos == self.tell():
                raise ValueError("parsing error, scanner is stuck")

    def finished(self):  # type: () -> bool
        """True if the cursor is at the end of the string, False otherwise."""
        return self._pos == self._size


BindingAccessorComponent = collections.namedtuple(
    "BindingAccessorComponent", ["kind", "value"])


class BindingAccessorPart(object):
    """Binding accessor part.

    The class constructor is given a binding accessor (e.g. "#.args[0]")
    and parses it.
    """

    __slots__ = ("path", "expression", "_scanner")

    def __init__(self, expression=None, scanner=None):
        # type: (Optional[str], Optional[StringScanner]) -> None
        self.path = []  # type: List[BindingAccessorComponent]
        self._scanner = scanner
        self.expression = expression
        self._parse(expression)

    _END_OF_EXPRESSION = re.compile(r"[ \|\),]")

    def _parse(self, expression):  # type: (Optional[str]) -> None
        """Parse a binding accessor part.

        It is internally converted to a series of components that are later
        resolved.
        """
        if self._scanner is None:
            if expression is None:
                raise ValueError(
                    "either expression or scanner must be passed as arguments")
            self._scanner = StringScanner(expression)

        start_pos = self._scanner.tell()

        # Check for scalar values first then variables.
        scalar = self._scan_scalar()
        if scalar:
            self.path.append(scalar)
        else:
            self._scan_push_variable()

        # Scan until something looks like a transform operator
        # or another transform parameter
        for _ in self._scanner.scan_until_regex(self._END_OF_EXPRESSION):
            self._scan_push_attribute()
            self._scan_push_indexes()

        # Do not consume the last character because it might be a transform
        # operator.
        if not self._scanner.finished():
            self._scanner.rewind(1)

        # Keep the expression and delete the scanner instance.
        self.expression = self._scanner.string[start_pos:self._scanner._pos]
        self._scanner = None

    _SQREEN_VARIABLE_REGEX = re.compile(r"#\.(\w+)")
    _PYTHON_IDENTIFIER_REGEX = re.compile(r"[a-zA-Z_](?:\w)*")

    def _scan_push_variable(self):  # type:  () -> None
        """Try to parse a variable and push it to the components list.

        Do nothing if the scanner cannot parse a variable or a Python
        identifier.
        """
        assert self._scanner is not None, "parsing is done"
        match = self._scanner.scan_regex(self._SQREEN_VARIABLE_REGEX)
        if match:
            variable_name = match.group(1)
            if variable_name == "cargs":
                # Hack for the PHP daemon using cargs instead of args.
                variable_name = "args"
            self.path.append(BindingAccessorComponent(
                kind="sqreen-variable",
                value=variable_name,
            ))
        else:
            match = self._scanner.scan_regex(self._PYTHON_IDENTIFIER_REGEX)
            if match:
                self.path.append(BindingAccessorComponent(
                    kind="variable",
                    value=match.group(),
                ))

    def _scan_push_attribute(self):  # type:  () -> None
        """Try to parse an attribute and push it to the components list.

        Do nothing of the scanner cannot parse a Python identifier.
        """
        assert self._scanner is not None, "parsing is done"
        while self._scanner.scan_string(".") is not None:
            match = self._scanner.scan_regex(self._PYTHON_IDENTIFIER_REGEX)
            if match:
                self.path.append(BindingAccessorComponent(
                    kind="attribute",
                    value=match.group(),
                ))

    _SCALAR_REGEX = re.compile(
        r"(?P<integer>-?\d+)|'(?P<string>(?:\\.|[^\\'])*)'|"
        "(?P<none>[Nn]one)|(?P<boolean>([Tt]rue)|([Ff]alse))"
    )
    _SCALAR_COERCE_FUNCS = {
        "integer": int,
        "none": lambda x: None,
        "boolean": lambda x: x == "True",
    }  # type: Dict[str, Callable[[Any], Any]]

    def _scan_scalar(self):  # type:  () -> Optional[BindingAccessorComponent]
        """Scan a scalar value and return the corresponding components.

        Return None if the scanner cannot parse an integer or a string.
        """
        assert self._scanner is not None, "parsing is done"
        match = self._scanner.scan_regex(self._SCALAR_REGEX)
        if match:
            last = match.lastgroup
            assert last is not None, "a group should have matched"
            value = match.group(last)
            coerce_func = self._SCALAR_COERCE_FUNCS.get(last)
            if coerce_func:
                value = coerce_func(value)
            return BindingAccessorComponent(kind="scalar", value=value)
        return None

    def _scan_push_indexes(self):  # type:  () -> None
        """Scan a sequence of indexes and push them to the components list."""
        assert self._scanner is not None, "parsing is done"
        while self._scanner.scan_string("[") is not None:
            scalar = self._scan_scalar()
            if scalar is None:
                raise ValueError("invalid index")
            if self._scanner.scan_string("]") is None:
                raise ValueError("unfinished index")
            self.path.append(scalar._replace(kind="index"))

    def resolve(self, **kwargs):  # type: (**Any) -> Any
        """Given a context, resolve the expression and return the value."""

        value = None
        for component in self.path:
            value = self._resolve_component(value, component, **kwargs)
        self._validate_value(value)
        return value

    def _resolve_component(self, value, component, **kwargs):
        # type: (Any, BindingAccessorComponent, Any) -> Any
        """Resolve a component.

        Simple expressions (static strings, integers, indexes and
        attributes) are directly resolved. Others are dispatched to specialized
        methods.
        """
        component_kind = component.kind
        if component_kind == "sqreen-variable":
            return self._resolve_sqreen_variable(component.value, **kwargs)
        elif component_kind == "index":
            return value[component.value]
        elif component_kind == "scalar":
            return component.value
        elif component_kind == "attribute":
            return getattr(value, component.value)
        elif component_kind == "variable":
            return self._resolve_variable(component.value, **kwargs)
        raise ValueError(
            "invalid component kind {!r}".format(component_kind)
        )

    _NO_VALUE = object()
    _SQREEN_VARIABLES = frozenset(["args", "kwargs", "request", "response", "rv", "data", "inst"])

    def _resolve_sqreen_variable(self, what, **kwargs):
        # type: (str, Any) -> Any
        """Resolve sqreen-variables (the ones starting with #.).

        Fall back on the request object if the value is not a special
        sqreen-variable. Return None if the request is None.
        """
        value = kwargs.get(what, self._NO_VALUE)
        if value is not self._NO_VALUE:
            return value
        elif what in self._SQREEN_VARIABLES:
            return None
        request = kwargs.get("request")
        if request is not None:
            return getattr(request, what)

    def _resolve_variable(self, variable_name, binding={}, global_binding={},
                          **kwargs):
        # type: (str, Mapping, Mapping, Any) -> Any
        """Resolve a general variable name.

        Search in local context first, then in general context.
        """
        value = binding.get(variable_name, self._NO_VALUE)
        if value is self._NO_VALUE:
            value = global_binding.get(variable_name, self._NO_VALUE)
            if value is self._NO_VALUE:
                raise NameError("name {!r} was not found in bindings"
                                .format(variable_name))
        return value

    def _validate_value(self, value):  # type: (Any) -> None
        """Raise ValueError if the value is a method or a function."""
        if isinstance(value, (types.FunctionType, types.MethodType)):
            raise ValueError("invalid return value {!r}".format(value))

    @property
    def pretty_expression(self):  # type: () -> str
        """Format the expression in a human readable way."""
        expression = []
        for item in self.path:
            if item.kind == "sqreen-variable":
                expression.append("#.{}".format(item.value))
            elif item.kind == "index":
                expression.append("[{}]".format(repr(item.value)))
            elif item.kind == "scalar":
                expression.append(repr(item.value))
            elif item.kind == "attribute":
                expression.append(".{}".format(item.value))
            elif item.kind == "variable":
                expression.append(item.value)
        return "".join(expression)

    def __repr__(self):  # type: () -> str
        return "{}({!r})".format(self.__class__.__name__, self.pretty_expression)


BindingAccessorTransform = collections.namedtuple("BindingAccessorTransform",
                                                  ["name", "func", "params"])


class BindingAccessor(object):
    """Binding accessors expression.

    The class constructor is given a binding accessor expression
    (e.g. "#.args[0] | len") and parses it.
    """

    __slots__ = ("parts", "expression", "_scanner")

    _TRANSFORM_FUNCS = {
        "int": transform_int,
        "len": transform_len,
        "flat_keys": flat_keys,
        "flat_values": flat_values,
        "default": transform_default,
        "type": transform_type,
        "encode": transform_encode,
        "pick": transform_pick,
    }  # type: Mapping[str, Callable]

    def __init__(self, expression=None, scanner=None):
        # type: (Optional[str], Optional[StringScanner]) -> None
        """Format the expression in a human readable way."""
        self.parts = []  # type: List[Union[BindingAccessorPart, BindingAccessorTransform]]
        self._scanner = scanner
        self.expression = expression
        self._parse(expression)

    _TRANSFORM_DELIMITER_REGEX = re.compile(r"\s*\|\s*")

    def _parse(self, expression):  # type: (Optional[str]) -> None
        if self._scanner is None:
            if expression is None:
                raise ValueError(
                    "either expression or scanner must be passed as arguments")
            self._scanner = StringScanner(expression)

        start_pos = self._scanner.tell()

        # We should always have a binding accessor as first element
        self._scan_push_binding_accessor()

        # Then, parse the transforms
        for _ in self._scanner.scan_until():
            if self._scanner.scan_regex(self._TRANSFORM_DELIMITER_REGEX):
                self._scan_push_transform()

        # Keep the expression and free the scanner
        self.expression = self._scanner.string[start_pos:self._scanner._pos]
        self._scanner = None

    def _scan_push_binding_accessor(self):  # type: () -> None
        assert self._scanner is not None, "parsing is done"
        self.parts.append(self._scan_binding_accessor())

    def _scan_binding_accessor(self):  # type: () -> BindingAccessorPart
        assert self._scanner is not None, "parsing is done"
        return BindingAccessorPart(scanner=self._scanner)

    _TRANSFORM_REGEX = re.compile(r"\w+")
    _TRANSFORM_PARAM_SEPARATOR_REGEX = re.compile(r",\s*")
    _TRANSFORM_END_OF_ARGS_REGEX = re.compile(r"\s*\)")

    def _scan_push_transform(self):  # type: () -> None
        assert self._scanner is not None, "parsing is done"
        match = self._scanner.scan_regex(self._TRANSFORM_REGEX)
        if match:
            transform_name = match.group()
            transform = self._TRANSFORM_FUNCS.get(transform_name)
            if transform is None:
                raise ValueError("unknown transformation {!r}".format(transform_name))
            params = []
            if self._scanner.scan_string("(") and not self._scanner.scan_regex(self._TRANSFORM_END_OF_ARGS_REGEX):
                params.append(self._scan_binding_accessor())
                for _ in self._scanner.scan_until_regex(self._TRANSFORM_END_OF_ARGS_REGEX):
                    if self._scanner.scan_regex(self._TRANSFORM_PARAM_SEPARATOR_REGEX):
                        params.append(self._scan_binding_accessor())
            self.parts.append(BindingAccessorTransform(transform_name, transform, params))

    def resolve(self, **kwargs):  # type: (Any) -> Any
        """Given a context, resolve the expression and return the value."""
        value = None
        exc = None
        for part in self.parts:
            try:
                if isinstance(part, BindingAccessorPart):
                    value = part.resolve(**kwargs)
                elif isinstance(part, BindingAccessorTransform):
                    value = part.func(value, exc, part.params, **kwargs)
            except Exception:
                exc = sys.exc_info()
            else:
                exc = None
        if exc:
            reraise(*exc)
        return value

    @property
    def pretty_expression(self):  # type: () -> str
        """Format the expression in a human readable way."""
        expression = []
        for part in self.parts:
            if isinstance(part, BindingAccessorPart):
                expression.append(part.pretty_expression)
            elif isinstance(part, BindingAccessorTransform):
                expression.append(" | {}".format(part.name))
                if part.params:
                    expression.append("({})".format(", ".join(
                        [a.pretty_expression for a in part.params])))
        return "".join(expression)

    def __repr__(self):  # type: () -> str
        return "{}({!r})".format(self.__class__.__name__, self.pretty_expression)
