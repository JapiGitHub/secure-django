# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Asynchronous variant of import_hook."""

from ..async_hook_point import async_hook_point
from .import_hook import ImportHookStrategy


class AsyncImportHookStrategy(ImportHookStrategy):
    """Asynchronous variant of ImportHookStrategy."""

    def import_hook_callback(self, original):
        return async_hook_point(self, self.hook_path, self.hook_name, original)
