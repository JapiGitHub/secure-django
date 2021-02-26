# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Patch an async event loop class with a context-aware task factory."""

import logging

from ..._vendors.wrapt import FunctionWrapper
from .import_hook import ImportHookStrategy

LOGGER = logging.getLogger(__name__)


def _patch_loop_cls(loop_cls):
    """Patch an async event loop class with a context-aware task factory.

    Return the modified class constructor.
    """
    orig_init = loop_cls.__init__
    orig_set_task_factory = loop_cls.set_task_factory

    def __init__wrapper(wrapped, instance, args, kwargs):
        wrapped(*args, **kwargs)
        instance.set_task_factory(None)

    def set_task_factory_wrapper(wrapped, instance, args, kwargs):
        from ...async_context import create_task_factory

        new_args = list(args)
        new_args[0] = create_task_factory(args[0])
        wrapped(*new_args, **kwargs)

    setattr(loop_cls, "__init__",
            FunctionWrapper(orig_init, __init__wrapper))
    setattr(loop_cls, "set_task_factory",
            FunctionWrapper(orig_set_task_factory, set_task_factory_wrapper))
    return loop_cls


class AsyncEventLoopStrategy(ImportHookStrategy):
    """Patch an async event loop class with a context-aware task factory."""

    def import_hook_callback(self, original):
        return _patch_loop_cls(original)
