# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Package for webserver detection
"""
from .base import FallbackWebServer
from .uwsgi_webserver import UWSGIWebServer

_webserver_classes = [
    UWSGIWebServer
]


def get_webserver():
    """Detect the currently running webserver."""
    for cls in _webserver_classes:
        obj = cls.detect()
        if obj is not None:
            return obj
    return FallbackWebServer()


__all__ = [cls.__name__ for cls in _webserver_classes] \
    + ["FallbackWebServer", "get_webserver"]
