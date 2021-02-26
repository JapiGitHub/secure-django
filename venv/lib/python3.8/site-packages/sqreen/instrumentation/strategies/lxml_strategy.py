# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" lxml strategy to add resolver callbacks
"""
import logging
import sys

from ..._vendors.wrapt import FunctionWrapper, getcallargs
from ...exceptions import AttackBlocked
from ..hook_point import execute_pre_callbacks
from .import_hook import ImportHookStrategy

LOGGER = logging.getLogger(__name__)


class ResolverCallbackMixin:
    """ lxml resolver called when XML entities are resolved.

    lxml.etree.XMLParser uses a resolver registry which is based on a set data
    structure.  Resolvers can be added and removed but it is not specified in
    what order they are called. In order to be called first, we report a hash
    value of 0 to be inserted as the first element of the hashtable
    underlying the set.
    """

    def __init__(self, strategy):
        self.strategy = strategy

    def __hash__(self):
        return 0

    def resolve(self, *args, **kwargs):
        options = {}
        action = execute_pre_callbacks(
            self.strategy.strategy_id,
            self.strategy.settings.get_callbacks(self.strategy.strategy_id)["pre"],
            None, args, kwargs, options
        )
        action_status = action.get("status")
        if action_status == "raise":
            LOGGER.debug(
                "Callback %s detected an attack", action.get("rule_name")
            )
            raise AttackBlocked(action.get("rule_name"))

        elif action_status == "override":
            return action.get("new_return_value")


class LXMLResolverStrategy(ImportHookStrategy):
    """ Strategy for adding a resolver to the lxml parser.
    """

    def import_hook_callback(self, original):
        etree = sys.modules["lxml.etree"]

        # the resolver must be a subclass of etree.Resolver otherwise
        # the parser refuses it so we create it at runtime.
        class ResolverCallback(ResolverCallbackMixin, etree.Resolver):
            pass

        resolver = ResolverCallback(self)

        # wrap the function to force add our resolver on the parser.
        def wrapper(wrapped, instance, args, kwargs):
            try:
                callargs = getcallargs(wrapped, *args, **kwargs)
                parser = callargs.get("parser")
                if parser is None:
                    parser = etree.get_default_parser()
                    kwargs["parser"] = parser
                resolvers = getattr(parser, "resolvers", None)
                if resolvers is not None:
                    resolvers.add(resolver)
            except Exception:
                LOGGER.debug("couldn't instrument lxml", exc_info=True)
            return wrapped(*args, **kwargs)

        return FunctionWrapper(original, wrapper)
