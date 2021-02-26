# -*- coding: utf-8 -*-
# Copyright (c) 2016, 2017, 2018, 2019 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Compatibility stub
"""
import sys

PYTHON_VERSION = sys.version_info[0]


if PYTHON_VERSION == 2:
    ALL_STRING_CLASS = basestring  # noqa
    STRING_CLASS = str
    UNICODE_CLASS = unicode  # noqa
elif PYTHON_VERSION == 3:
    ALL_STRING_CLASS = str
    STRING_CLASS = str
    UNICODE_CLASS = str
