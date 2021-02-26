# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Base webserver module
"""


class BaseWebServer(object):
    """Base class for webservers."""

    def various_infos(self):
        """Returns information sent during startup."""
        return {
            "name": "unknown",
        }

    @classmethod
    def detect(cls):
        """Returns an instance if the webserver was detected."""
        return cls()


class FallbackWebServer(BaseWebServer):
    """Default webserver if none was detected."""
