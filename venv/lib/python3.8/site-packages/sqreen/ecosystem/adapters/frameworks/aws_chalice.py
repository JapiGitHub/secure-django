# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""
AWS Chalice static instrumentation
"""
import sys

from ....rules_callbacks.sqreen_error_page import BaseSqreenErrorPage


class AWSChaliceSqreenErrorPage(BaseSqreenErrorPage):

    def pre(self, instance, args, kwargs, options):
        ret = self.handle_exception(sys.exc_info()[1])
        if ret is not None:
            from chalice import Response

            status_code, body, headers = ret
            return {
                "status": "override",
                "new_return_value": Response(
                    body, headers=headers, status_code=status_code)
            }


class AWSChaliceFrameworkAdapter:

    def instrumentation_callbacks(self, runner, storage):
        return [
            AWSChaliceSqreenErrorPage.from_rule_dict({
                "name": "ecosystem_aws_chalice_sqreen_error_page",
                "rulespack_id": "ecosystem/framework",
                "block": True,
                "test": False,
                "hookpoint": {
                    "klass": "chalice.app::RestAPIEventHandler",
                    "method": "_unhandled_exception_to_response",
                },
                "callbacks": {},
                "priority": 100,
            }, runner, storage),
        ]
