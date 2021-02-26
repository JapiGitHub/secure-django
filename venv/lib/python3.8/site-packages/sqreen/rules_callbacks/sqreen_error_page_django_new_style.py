# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Custom error page for Django new style middlewares
"""
from .headers_insert import convert_to_str
from .sqreen_error_page import BaseSqreenErrorPage


class SqreenErrorPageDjangoNewStyle(BaseSqreenErrorPage):

    def pre(self, instance, args, kwargs, options):

        exc = args[1]
        ret = self.handle_exception(exc)

        if ret is not None:
            status_code, content, headers = ret

            from django.http import HttpResponse  # type: ignore

            response = HttpResponse(content)
            response.status_code = status_code

            if headers:
                for header_name, header_value in convert_to_str(headers.items()):
                    response[header_name] = header_value

            return {
                "status": "override",
                "new_return_value": response
            }
