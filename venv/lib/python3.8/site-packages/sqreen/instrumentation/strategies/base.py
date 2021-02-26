# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Base strategy
"""
import logging

LOGGER = logging.getLogger(__name__)


class BaseStrategy(object):
    """ The base strategy holds callbacks for a hook point

    Subclasses need to define way to hook.
    BaseStrategy accepts a channel, usually passed from Instrumentation
    directly.
    """

    def __init__(self, strategy_id, settings, import_hook, before_hook_point=None):
        self.strategy_id = strategy_id
        self.settings = settings
        self.import_hook = import_hook
        self._before_hook_point = before_hook_point

    def before_hook_point(self):
        """ Run code just before running a hook_point
        """
        if self._before_hook_point is not None:
            self._before_hook_point()

    @classmethod
    def get_strategy_id(cls, callback):
        raise NotImplementedError

    @classmethod
    def get_early_strategy_id(cls):
        return None
