# -*- coding: utf-8 -*-
# Copyright (c) 2016, 2017, 2018, 2019 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Binding for the WAF Input Data Structure
"""
import ctypes

from ._compat import UNICODE_CLASS
from ._ffi import pw_createArray, pw_createInt, pw_createUint, pw_createMap, \
        pw_createStringWithLength, pw_addArray, pw_addMap, pw_freeArg


def create_string(value, max_string_length=4096):
    if isinstance(value, UNICODE_CLASS):
        value = value[:max_string_length].encode("utf-8", errors="surrogatepass")

    if not isinstance(value, bytes):
        raise ValueError("value must be a string or bytes")

    value = value[:max_string_length]
    return pw_createStringWithLength(value, len(value))


def append_to_map(array, key, value):
    if isinstance(key, UNICODE_CLASS):
        key = key.encode("utf-8", errors="surrogatepass")

    if not isinstance(key, bytes):
        raise ValueError("value must be a string or bytes")

    return pw_addMap(ctypes.byref(array), key, 0, value)


def free(value):
    pw_freeArg(ctypes.byref(value))


def create(value, max_depth=10, ignore_none=True, max_string_length=4096,
           max_items=150):
    """ Lower-level function to convert a Python value to input value
    """
    if isinstance(value, str) or isinstance(value, bytes):
        return create_string(value, max_string_length=max_string_length)

    if isinstance(value, bool):
        return pw_createUint(ctypes.c_uint64(int(value)))

    if isinstance(value, int):
        if value < 0:
            return pw_createInt(ctypes.c_int64(value))
        else:
            return pw_createUint(ctypes.c_uint64(value))

    if isinstance(value, list) or isinstance(value, tuple):
        obj = pw_createArray()
        if max_depth <= 0:
            # ignore if deeply nested
            return obj
        for i, item in enumerate(value):
            if i >= max_items or (item is None and ignore_none):
                continue
            item_obj = create(item, max_depth=max_depth - 1)
            ret = pw_addArray(ctypes.byref(obj), item_obj)
            if ret is False:
                free(item_obj)
        return obj

    if isinstance(value, dict):
        obj = pw_createMap()
        if max_depth <= 0:
            # ignore if deeply nested
            return obj
        for i, (k, v) in enumerate(value.items()):
            if i >= max_items or (v is None and ignore_none):
                continue
            item_obj = create(v, max_depth=max_depth - 1)
            ret = append_to_map(obj, k, item_obj)
            if ret is False:
                free(item_obj)
        return obj

    return create_string(UNICODE_CLASS(value), max_string_length=max_string_length)


class Input:
    """
    Higher-level bridge between Python values and input values (PWArgs).
    """

    def __init__(self, obj):
        self._obj = obj
        self.owned = False

    def __del__(self):
        # If the PWArgs is owned, it must not be freed
        if self._obj is None or self.owned:
            return
        free(self._obj)
        self._obj = None

    @classmethod
    def from_python(cls, value, **kwargs):
        """ Convert a Python value to a managed input.
        """
        return cls(create(value, **kwargs))

    def __repr__(self):
        return "<{} obj={!r}>".format(self.__class__.__name__, self._obj)


# Alias for versions <1.0
PWArgs = Input

__all__ = ["Input"]
