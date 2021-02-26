# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Insert custom headers for aiohttp."""

import logging

from .headers_insert import BaseHeadersInsertCB

LOGGER = logging.getLogger(__name__)


class HeadersInsertCBAioHTTP(BaseHeadersInsertCB):
    def post(self, instance, args, kwargs, options):
        """Insert custom headers."""
        try:
            response = options.get("result")
            for header_name, header_value in self.headers.values():
                response.headers[header_name] = header_value
        except Exception:
            LOGGER.warning("An error occurred", exc_info=True)

        return {}
