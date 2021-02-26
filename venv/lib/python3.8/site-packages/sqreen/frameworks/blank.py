# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Blank request for callbacks needing a request when no one is present
"""

from .base import BaseRequest, BaseResponse


class BlankRequest(BaseRequest):

    @property
    def raw_headers(self):
        return {}

    @property
    def raw_client_ip(self):
        return None

    @property
    def client_user_agent(self):
        return None

    @property
    def cookies_params(self):
        return {}

    @property
    def body(self):
        return None

    @property
    def form_params(self):
        return {}

    @property
    def hostname(self):
        return None

    @property
    def method(self):
        return None

    @property
    def path(self):
        return None

    @property
    def query_params(self):
        return {}

    @property
    def query_params_values(self):
        return []

    @property
    def referer(self):
        return None

    @property
    def remote_port(self):
        return None

    @property
    def remote_addr(self):
        return None

    @property
    def scheme(self):
        return None

    @property
    def server_port(self):
        return None

    @property
    def view_params(self):
        return {}

    @property
    def json_params(self):
        return {}


class BlankResponse(BaseResponse):

    @property
    def status_code(self):
        return None

    @property
    def content_type(self):
        return None

    @property
    def content_length(self):
        return None
