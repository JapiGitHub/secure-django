# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Django Framework Adapter
"""

from ....rules_callbacks import BindingAccessorProvideData
from ..transports.framework import FrameworkTransportCallback


class DjangoFrameworkAdapter:

    def instrumentation_callbacks(self, runner, storage):
        return [
            FrameworkTransportCallback.from_rule_dict({
                "name": "ecosystem_django_wsgi",
                "rulespack_id": "ecosystem/transport",
                "block": False,
                "test": False,
                "hookpoint": {
                    "klass": "django.core.handlers.wsgi::WSGIHandler",
                    "method": "__call__",
                    "strategy": "wsgi"
                },
                "callbacks": {},
            }, runner, storage),
            BindingAccessorProvideData.from_rule_dict({
                "name": "ecosystem_request_django",
                "data": {
                    "values": [
                        ["pre", [
                            ["server.request.client_ip", "#.client_ip"],
                            ["server.request.method", "#.method"],
                            ["server.request.uri.raw", "#.request_uri"],
                            ["server.request.headers.no_cookies", "#.headers_no_cookies"],
                            ["server.request.cookies", "#.cookies_params"],
                            ["server.request.query", "#.query_params"],
                            ["server.request.body", "#.body_params"],
                            ["server.request.body.raw", "#.body"],
                            ["server.request.body.files_field_names", "#.files_field_names"],
                            ["server.request.body.filenames", "#.filenames"],
                            ["server.request.body.combined_file_size", "#.combined_file_size"],
                            ["server.request.path_params", "#.view_params"],
                        ]]
                    ]
                },
                "rulespack_id": "ecosystem/transport",
                "block": True,
                "hookpoint": {
                    "klass": "django.core.handlers.base::BaseHandler",
                    "method": "load_middleware",
                    "strategy": "django"
                },
                "priority": 100,
            }, runner, storage),
            BindingAccessorProvideData.from_rule_dict({
                "name": "ecosystem_response_django",
                "data": {
                    "values": [
                        ["post", [
                            ["server.response.status", "#.response.status_code"],
                            ["server.response.headers.no_cookies", "#.response.headers_no_cookies"],
                            ["server.response.body.raw", "#.response.body"],
                        ]]
                    ]
                },
                "rulespack_id": "ecosystem/transport",
                "block": True,
                "hookpoint": {
                    "klass": "django.core.handlers.base::BaseHandler",
                    "method": "load_middleware",
                    "strategy": "django"
                },
                "priority": 40,
            }, runner, storage),
        ]
