# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Base framework strategy
"""
import logging

from .import_hook import BaseStrategy

LOGGER = logging.getLogger(__name__)


class HookpointMismatchError(Exception):
    """ Raised when a callback is trying to be added for a strategy and their
    hookpoint are not the same
    """

    pass


class FrameworkStrategy(BaseStrategy):
    """ Specific strategy for framework instrumentation. They hook on atrributes
    defined in the class, MODULE_NAME, HOOK_CLASS, HOOK_METHOD. They wrap the
    resulting object with self.wrapper by passing original as first argument and
    a middleware for the correct framework as second argument
    """

    def __init__(self, *args, **kwargs):
        super(FrameworkStrategy, self).__init__(*args, **kwargs)
        self.import_hook.register_patcher(
            self.MODULE_NAME,
            self.HOOK_CLASS,
            self.HOOK_METHOD,
            self.import_hook_callback,
        )

    @staticmethod
    def middleware(original):
        raise NotImplementedError

    @staticmethod
    def wrapper(original, middleware):
        return middleware(original)

    def import_hook_callback(self, original):
        """ Monkey-patch the object located at hook_class.hook_name on an
        already loaded module
        """
        return self.wrapper(original, self.middleware)

    @classmethod
    def get_strategy_id(cls, callback):
        """ This strategy only hook on
        (cls.MODULE_NAME::cls.HOOK_CLASS, cls.HOOK_METHOD)
        """
        # Check that callback hookpoint and strategy hookpoint match
        strategy_module = "{}::{}".format(cls.MODULE_NAME, cls.HOOK_CLASS)
        mismatch_module = callback.hook_module != strategy_module
        mismatch_method = callback.hook_name != cls.HOOK_METHOD
        if mismatch_module or mismatch_method:
            err_msg = "Callback hookpoint ({}, {}) doesn't match strategy callback ({}, {})"
            msg = err_msg.format(
                callback.hook_module,
                callback.hook_name,
                strategy_module,
                cls.HOOK_METHOD,
            )
            raise HookpointMismatchError(msg)
        return (
            "{}::{}".format(cls.MODULE_NAME, cls.HOOK_CLASS),
            cls.HOOK_METHOD,
        )

    @classmethod
    def get_early_strategy_id(cls):
        return (
            "{}::{}".format(cls.MODULE_NAME, cls.HOOK_CLASS),
            cls.HOOK_METHOD,
        )
