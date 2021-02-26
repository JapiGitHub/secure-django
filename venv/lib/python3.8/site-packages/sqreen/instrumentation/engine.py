# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Instrumentation helper responsible for adding dynamic callback
"""
import logging
from bisect import bisect
from collections import defaultdict

from ..utils import HAS_ASYNCIO, itervalues
from .import_hook import ModuleFinder
from .strategies import (
    AWSLambdaStrategy,
    DBApi2Strategy,
    DjangoStrategy,
    FlaskStrategy,
    ImportHookStrategy,
    LXMLResolverStrategy,
    Psycopg2Strategy,
    PyramidStrategy,
    WSGIFactoryStrategy,
    WSGIReceiverStrategy,
    WSGIStrategy,
)

STRATEGIES = {
    "aws_lambda": AWSLambdaStrategy,
    "import_hook": ImportHookStrategy,
    "DBApi2": DBApi2Strategy,
    "django": DjangoStrategy,
    "psycopg2": Psycopg2Strategy,
    "flask": FlaskStrategy,
    "pyramid": PyramidStrategy,
    "wsgi": WSGIStrategy,
    "wsgi_factory": WSGIFactoryStrategy,
    "wsgi_receiver": WSGIReceiverStrategy,
    "lxml_resolver": LXMLResolverStrategy,
}

if HAS_ASYNCIO:
    from .strategies import (
        AioHTTPHookStrategy,
        AioHTTPInstallStrategy,
        AsyncEventLoopStrategy,
        AsyncImportHookStrategy,
    )

    STRATEGIES.update({
        "async_event_loop": AsyncEventLoopStrategy,
        "async_import_hook": AsyncImportHookStrategy,
        "aiohttp_install": AioHTTPInstallStrategy,
        "aiohttp_hook": AioHTTPHookStrategy,
    })

LOGGER = logging.getLogger(__name__)


class InstrumentationSettings(object):

    def __init__(self, instrumentation):
        self._callbacks = defaultdict(lambda: defaultdict(list))
        self.instrumentation = instrumentation

    def get_callbacks(self, hook_key):
        return self._callbacks[hook_key]

    def add_callback(self, callback):
        """ Add a callback. The callback defines itself where it should
        hook to and the strategy use for hooking (set_attr or DBApi2)
        """
        self.instrumentation._load_strategy(callback)
        hook_key = (callback.hook_module, callback.hook_name)
        method_callbacks = self._callbacks[hook_key]
        for method in callback.lifecycle_methods:
            callbacks = method_callbacks[method]
            idx = bisect([c.priority for c in callbacks], callback.priority)
            callbacks.insert(idx, callback)

    def remove_callback(self, callback):
        """
        Remove a given callback associated with the strategy
        """
        hook_key = (callback.hook_module, callback.hook_name)
        for callbacks in itervalues(self._callbacks[hook_key]):
            try:
                callbacks.remove(callback)
            except ValueError:
                pass

    def remove_callbacks(self):
        """
        Remove all callbacks.
        """
        self._callbacks.clear()

    def __enter__(self):
        self._tmp = self.__class__(self.instrumentation)
        return self._tmp

    def __exit__(self, exc_type, exc_value, traceback):
        """ Apply the current settings if everything went fine.
        """
        tmp = self.__dict__.pop("_tmp", None)
        if tmp is None or exc_type is not None:
            # Forget about the new settings
            return
        # Load missing hookpoints
        self.instrumentation.hook_all()
        # Atomic callbacks switch
        self._callbacks = tmp._callbacks


class Instrumentation(object):
    """ The instrumentation class is the exposed face of the
    instrumentation engine. It dispatchs to the right strategy,
    the default one is set_attr.

    The instrument class dispatch to different strategies based on strategy
    name defined in callback. It ask stategy for an unique id based on hook path
    infos and ensure to have only one strategy instance per id. It's needed
    for DBApi2 strategy where every sqlite3 callbacks will be stored in the same
    strategy to avoid double-instrumentation.

    It also instantiate a global ImportHook that strategy will register
    against when hooking.
    """

    def __init__(self, before_hook_point=None):
        self.strategies = {}
        self.before_hook_point = before_hook_point
        self.import_hook = ModuleFinder()
        self.settings = InstrumentationSettings(self)
        self._load_early_strategies()

    @property
    def enabled(self):
        return not not self.settings._callbacks

    def hook_all(self):
        self.import_hook.inject()
        self.import_hook.apply_patchers()

    def _load_early_strategies(self):
        """ Load the instrumentation strategies that must be initialized very early
        and cannot wait for a callback to be instantiated.
        """
        for strategy_cls in itervalues(STRATEGIES):
            strategy_id = strategy_cls.get_early_strategy_id()
            if strategy_id is not None:
                self.strategies[strategy_id] = strategy_cls(
                    strategy_id,
                    self.settings,
                    self.import_hook,
                    self.before_hook_point
                )

    def _load_strategy(self, callback):
        """ Load the instrumentation strategy for a callback if it
        was not loaded before.
        """
        strategy_class = self._get_strategy_class(callback.strategy)

        # Get the strategy id
        strategy_id = strategy_class.get_strategy_id(callback)

        # Check if we already have a strategy
        strategy_instance = self.strategies.get(strategy_id)
        if strategy_instance is None:
            self.strategies[strategy_id] = strategy_instance = strategy_class(
                strategy_id,
                self.settings,
                self.import_hook,
                self.before_hook_point
            )

    @staticmethod
    def _get_strategy_class(strategy):
        """ Return a strategy class depending on the strategy name passed
        in parameter.
        Raise a NotImplementedError if the strategy is unknown.
        """
        strategy_cls = STRATEGIES.get(strategy)
        if strategy_cls is None:
            raise NotImplementedError(
                "Unknown hooking strategy {!r}".format(strategy))
        return strategy_cls
