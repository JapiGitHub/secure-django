# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Custom error page for Flask
"""
from .headers_insert import convert_to_str
from .sqreen_error_page import BaseSqreenErrorPage


class SqreenErrorPageFlask(BaseSqreenErrorPage):

    def pre(self, instance, args, kwargs, options):

        exception = args[0]
        ret = self.handle_exception(exception)

        if ret is not None:
            status_code, content, headers = ret

            from flask import make_response

            response = make_response(content)
            response.status_code = status_code

            for header_name, header_value in convert_to_str(headers.items()):
                response.headers[header_name] = header_value

            return {
                "status": "override",
                "new_return_value": response
            }
