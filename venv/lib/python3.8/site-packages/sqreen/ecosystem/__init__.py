# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#

from .adapters import init as init_adapters
from .tracers import init as init_tracers


def init(interface_manager):
    """ Sqreen ecosystem module initialization
    """
    init_adapters(interface_manager)
    init_tracers(interface_manager)
