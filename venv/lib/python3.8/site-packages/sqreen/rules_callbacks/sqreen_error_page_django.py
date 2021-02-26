# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Custom error page for Django
"""
from .headers_insert import convert_to_str
from .sqreen_error_page import BaseSqreenErrorPage


class SqreenErrorPageDjango(BaseSqreenErrorPage):

    def pre(self, instance, args, kwargs, options):

        exc_info = args[2]
        if not exc_info:
            return

        ret = self.handle_exception(exc_info[1])

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
