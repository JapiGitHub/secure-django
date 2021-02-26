# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Base custom error page
"""
import sys
from os.path import dirname, join

from ..exceptions import ActionRedirect, RequestBlocked
from ..frameworks.wsgi import WSGIResponse
from ..rules import RuleCallback
from ..rules_actions import RecordObservationMixin

if sys.version_info >= (3, 0):
    from http.client import responses as HTTP_STATUS_CODE
else:
    from httplib import responses as HTTP_STATUS_CODE


class BaseSqreenErrorPage(RecordObservationMixin, RuleCallback):

    INTERRUPTIBLE = False
    DEFAULT_RULE_DATA = {
        "type": "custom_error_page",
        "status_code": 403,
    }

    def __init__(self, *args, **kwargs):
        super(BaseSqreenErrorPage, self).__init__(*args, **kwargs)
        with open(join(dirname(__file__), "sqreen_error_page.html"), "r") as f:
            self.content = f.read()

        rule_data = self.DEFAULT_RULE_DATA
        values = self.data.get("values")
        if values:
            rule_data = values[0]

        self.rule_type = rule_data.get("type", self.DEFAULT_RULE_DATA["type"])

        if self.rule_type == "custom_error_page":
            self.status_code = int(rule_data.get(
                "status_code", self.DEFAULT_RULE_DATA["status_code"]))
            self.storage.attack_http_code = self.status_code
        elif self.rule_type == "redirection" and "redirection_url" in rule_data:
            self.redirection_url = rule_data["redirection_url"]
        else:
            raise ValueError("Invalid rule_type %s" % self.rule_type)

    def handle_exception(self, exception):
        if exception is None or not isinstance(exception, RequestBlocked):
            return None

        exception.done()
        if isinstance(exception, ActionRedirect):
            headers = {"Location": exception.target_url}
            self.record_observation("http_code", "303", 1)
            return (303, "", headers)
        # Else, exception is either ActionBlock or AttackBlocked.
        elif self.rule_type == "custom_error_page":
            self.record_observation("http_code", str(self.status_code), 1)
            return (self.status_code, self.content, {"Content-Type": "text/html"})
        elif self.rule_type == "redirection":
            headers = {"Location": self.redirection_url}
            self.record_observation("http_code", "303", 1)
            return (303, "", headers)


class SqreenErrorPage(BaseSqreenErrorPage):

    def failing(self, instance, args, kwargs, options):
        exc_info = options.get("exc_info")
        ret = self.handle_exception(exc_info[1])
        if ret is not None:
            # Pylons tweak to bypass the StatusCodeRedirect middleware
            environ = args[0]
            environ["pylons.status_code_redirect"] = None

            status_code, body, headers = ret
            status_msg = HTTP_STATUS_CODE.get(status_code)
            if status_msg is not None:
                status = "{} {}".format(status_code, status_msg)
            else:
                status = "500 Internal Server Error"
            return {
                "status": "override",
                "new_return_value": WSGIResponse(status, headers, body.encode("utf-8"))
            }
