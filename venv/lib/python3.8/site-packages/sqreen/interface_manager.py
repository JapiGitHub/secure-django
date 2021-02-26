# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Sqreen Agent Interfaces
"""
import logging

LOGGER = logging.getLogger(__name__)


class InterfaceManager:

    def __init__(self):
        self.modules = []

    def register(self, module):
        self.modules.append(module)

    def call(self, method, *args, **kwargs):
        """ Call all registered modules in order of insertion until a method
        returns a value (not None).
        """
        try:
            it = [r for r in self.call_all(method, *args, **kwargs) if r is not None]
            return next(iter(it))
        except StopIteration:
            return None

    def call_all(self, method, *args, **kwargs):
        """ Call all registered module methods and return an iterator with all
        results.
        """
        for module in self.modules:
            func = getattr(module, method, None)
            if func is not None:
                yield func(*args, **kwargs)
