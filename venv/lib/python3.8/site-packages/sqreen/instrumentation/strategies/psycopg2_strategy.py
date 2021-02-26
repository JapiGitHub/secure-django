# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Custom strategy for psycopg2 oddities
"""
import logging

from ..._vendors.wrapt import FunctionWrapper
from .dbapi2 import CustomConnectionBase, CustomCursorBase, DBApi2Strategy

LOGGER = logging.getLogger(__name__)


def wrap_register_type(original):
    def _extract(obj, conn_or_cursor=None):
        return obj, conn_or_cursor

    def wrapper(wrapped, instance, args, kwargs):
        obj, conn_or_cursor = _extract(*args, **kwargs)
        if isinstance(conn_or_cursor, (CustomConnectionBase, CustomCursorBase)):
            conn_or_cursor = conn_or_cursor.__wrapped__
        return wrapped(obj, conn_or_cursor)

    return FunctionWrapper(original, wrapper)


def wrap_quote_ident(original):
    def _extract(ident, scope):
        return ident, scope

    def wrapper(wrapped, instance, args, kwargs):
        ident, scope = _extract(*args, **kwargs)
        if isinstance(scope, (CustomConnectionBase, CustomCursorBase)):
            scope = scope.__wrapped__
        return wrapped(ident, scope)

    return FunctionWrapper(original, wrapper)


def wrap_as_string(original):

    def wrapper(wrapped, instance, args, kwargs):
        context = args[0] if args else kwargs.get("context")
        if isinstance(context, (CustomConnectionBase, CustomCursorBase)):
            context = context.__wrapped__
        return wrapped(context)

    return FunctionWrapper(original, wrapper)


class Psycopg2Strategy(DBApi2Strategy):
    """ Dedicated DBApi2 strategy for psycopg2.
    """

    def __init__(self, *args, **kwargs):
        super(Psycopg2Strategy, self).__init__(*args, **kwargs)
        # Monkey-patch psycopg2.*.register_type functions
        self.import_hook.register_patcher(
            "{}.extensions".format(self.module_path), None,
            "register_type", wrap_register_type)
        self.import_hook.register_patcher(
            "{}._psycopg2".format(self.module_path), None,
            "register_type", wrap_register_type)
        self.import_hook.register_patcher(
            "{}._json".format(self.module_path), None,
            "register_type", wrap_register_type)
        self.import_hook.register_patcher(
            "{}._range".format(self.module_path), None,
            "register_type", wrap_register_type)
        self.import_hook.register_patcher(
            "{}._ipaddress".format(self.module_path), None,
            "register_type", wrap_register_type)
        # Monkey-patch psycopg2.*.quote_ident functions
        self.import_hook.register_patcher(
            "{}.extensions".format(self.module_path), None,
            "quote_ident", wrap_quote_ident)
        self.import_hook.register_patcher(
            "{}.extras".format(self.module_path), None,
            "quote_ident", wrap_quote_ident)
        # Monkey-patch psycopg2.sql.Literal.as_string function
        self.import_hook.register_patcher(
            "{}.sql".format(self.module_path), "Literal",
            "as_string", wrap_as_string)
