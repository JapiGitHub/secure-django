# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" uWSGI webserver module
"""
from .base import BaseWebServer

WHITELISTED_OPTS = [
    "enable-threads",
    "lazy-apps",
    "master",
    "py-call-osafterfork",
]


class UWSGIWebServer(BaseWebServer):
    """uWSGI webserver."""

    def __init__(self, module):
        self._module = module

    def various_infos(self):
        """Gather various information about uwsgi."""
        opts = getattr(self._module, "opt", {})
        return {
            "name": "uwsgi",
            "version": getattr(self._module, "version", "unknown"),
            "options": {opt: opts.get(opt) for opt in WHITELISTED_OPTS
                        if opt in opts},
        }

    @classmethod
    def detect(cls):
        """Detect if uwsgi module is present."""
        try:
            import uwsgi  # type: ignore
        except ImportError:
            return None
        return cls(module=uwsgi)
