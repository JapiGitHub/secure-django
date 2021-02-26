# -*- coding: utf-8 -*-
# Copyright (c) 2016, 2017, 2018, 2019 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Sqreen Python Native Module"""
import ctypes
import logging
import os
import sys
import sysconfig

try:
    import pkg_resources
except ImportError:
    pkg_resources = None  # pragma: no cover

from . import __about__

LOGGER = logging.getLogger("sqreen.native.ffi")


def _get_libc_name():
    """Return the libc of the system."""
    target = sysconfig.get_config_var("HOST_GNU_TYPE")
    if target is not None and target.endswith("musl"):
        return "muslc"
    return "glibc"


def _get_lib_path(name):
    """Return the path of the library called `name`."""
    if os.name == "posix" and sys.platform == "darwin":
        prefix, ext = "lib", ".dylib"
    elif sys.platform == "win32":
        prefix, ext = "", ".dll"
    else:
        prefix, ext = "lib", ".{}.so".format(_get_libc_name())
    fn = None
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        fn = os.path.join(meipass, prefix + name + ext)
    if fn is None and pkg_resources is not None:
        fn = pkg_resources.resource_filename("sq_native", prefix + name + ext)
    if fn is None:
        root_dir = os.path.dirname(os.path.abspath(__file__))
        fn = os.path.join(root_dir, prefix + name + ext)
    return fn


def _load_library(name):
    """Load a native library located in this module."""
    path = _get_lib_path(name)
    if path is None or not os.path.exists(path):
        raise RuntimeError("Native library not available at {}".format(path))
    return ctypes.cdll.LoadLibrary(path)


# defined manually because the value field is declared as a union.
# It must be kept up-to-date with the library header file.
class _PWArgs(ctypes.Structure):
    _fields_ = [
        ("parameterName", ctypes.POINTER(ctypes.c_char)),
        ("parameterNameLength", ctypes.c_uint64),
        ("value", ctypes.c_void_p),
        ("nbEntries", ctypes.c_uint64),
        ("type", ctypes.c_int),
    ]

PW_LOG_FUNC = ctypes.CFUNCTYPE(
    None, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p,
    ctypes.c_int, ctypes.c_char_p, ctypes.c_size_t)


# stage 1: load the library then import bindings
_lib = _load_library("Sqreen")

from ._bindings import *

# stage 2: check library version and setup logging if required
def get_lib_version():
    # type: () -> str
    """Get the library version as a string."""
    return "{0.major}.{0.minor}.{0.patch}".format(pw_getVersion())

_lib_version = get_lib_version()
if _lib_version != __about__.__lib_version__:
    raise RuntimeError("Native library version mismatch: {} != {}"
                       .format(_lib_version, __about__.__lib_version__))
