# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Deliverer classes package
"""
from .batch import BatchDeliverer
from .simple import SimpleDeliverer

__all__ = ["SimpleDeliverer", "BatchDeliverer"]


def get_deliverer(batch_size, max_staleness, session):
    """ Helper function to returns the correct deliverer class for the
    batch_size and max_stalennes parameters
    """
    if batch_size < 1:
        return SimpleDeliverer(session)
    else:
        return BatchDeliverer(session, batch_size, max_staleness)
