# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Custom error page for aiohttp."""

from logging import getLogger

from .headers_insert import convert_to_str
from .sqreen_error_page import BaseSqreenErrorPage

LOGGER = getLogger(__name__)


class SqreenErrorPageAioHTTP(BaseSqreenErrorPage):
    """Custom error page for aiohttp."""

    def pre(self, instance, args, kwargs, options):

        exc = kwargs.get("exc") or args[2]
        ret = self.handle_exception(exc)

        if ret is not None:
            status_code, content, headers = ret

            from aiohttp.web_response import Response  # type: ignore

            content_type = headers.get("Content-Type", "text/html")
            resp = Response(status=status_code, content_type=content_type,
                            body=content.encode("utf-8"))
            for header_name, header_value in convert_to_str(headers.items()):
                resp.headers[header_name] = header_value
            return {
                "status": "override",
                "new_return_value": resp
            }
