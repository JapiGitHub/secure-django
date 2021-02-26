# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Log data from the Reactive Engine
"""
import logging

from ..rules import ReactiveRuleCallback

LOGGER = logging.getLogger(__name__)


class ReactiveLog(ReactiveRuleCallback):

    def handler(self, instance, args, kwargs, options):
        LOGGER.info("Reactive data: %r", args[0])
