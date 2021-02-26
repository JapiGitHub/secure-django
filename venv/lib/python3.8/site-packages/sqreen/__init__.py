# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Sqreen python agent package
"""
from .__about__ import __author__, __email__, __version__
from .runner_thread import start
from .sdk.auth import auth_track, identify, signup_track
from .sdk.events import track

__all__ = [
    "__author__",
    "__email__",
    "__version__",
    "start",
    "identify",
    "auth_track",
    "signup_track",
    "track",
]
