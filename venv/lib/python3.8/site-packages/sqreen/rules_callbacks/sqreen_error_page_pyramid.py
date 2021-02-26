# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Custom error page for Pyramid
"""
from .headers_insert import convert_to_str
from .sqreen_error_page import BaseSqreenErrorPage


class SqreenErrorPagePyramid(BaseSqreenErrorPage):

    def pre(self, instance, args, kwargs, options):

        context = args[2]
        ret = self.handle_exception(context)

        if ret is not None:
            status_code, content, headers = ret

            from pyramid.response import Response  # type: ignore

            response = Response(content, status_code=status_code)

            for header_name, header_value in convert_to_str(headers.items()):
                response.headers[header_name] = header_value

            return {
                "status": "override",
                "new_return_value": response
            }
