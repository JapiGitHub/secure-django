# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Instrumentation helpers
"""
import threading

LOCAL = threading.local()
NOT_EXECUTED = {"status": "not_executed"}


def guard_call(key, callback, *args, **kwargs):
    """ Conditionnaly call callback checking that it cannot be called
    recursively
    """
    d = LOCAL.__dict__
    if key in d:
        return NOT_EXECUTED

    d[key] = None
    try:
        return callback(*args, **kwargs)
    finally:
        d.pop(key, None)
