# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#

from .frameworks import init as init_frameworks
from .transports import init as init_transports


def init(interface_manager):
    """ Sqreen ecosystem adapters initialization
    """
    init_frameworks(interface_manager)
    init_transports(interface_manager)
