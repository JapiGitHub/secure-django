# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Generic WSGI HTTP Request / Response stuff
"""
import logging
import sys

from ..utils import Iterable, Mapping, cached_property, to_unicode_safe
from .base import BaseRequest, BaseResponse

if sys.version_info[0] >= 3:
    from http.cookies import SimpleCookie
    from urllib.parse import parse_qs, quote
else:
    from urllib import quote

    from Cookie import SimpleCookie
    from urlparse import parse_qs


LOGGER = logging.getLogger(__name__)


class BaseWSGIRequest(BaseRequest):
    """ Base class for WSGI based framework requests.
    """

    @property
    def form_params(self):
        # TODO: use a fallback form parser (like FormDataParser from werkzeug)
        # to parse the body when form params cannot be retrieved from the
        # framework.
        # Returns an empty dict for now.
        return {}

    @cached_property
    def query_params(self):
        raw_query = self.get_raw_header("QUERY_STRING", "")
        try:
            return parse_qs(raw_query)
        except Exception:
            LOGGER.debug(
                "couldn't parse URL query %s", raw_query, exc_info=True
            )
            return {}

    @property
    def view_params(self):
        return {}

    @cached_property
    def cookies_params(self):
        cookies = self.get_raw_header("HTTP_COOKIES")
        if cookies:
            try:
                cookie = SimpleCookie()
                cookie.load(cookies)
                return {key: cookie[key].coded_value for key in cookie.keys()}
            except Exception:
                LOGGER.debug("couldn't parse cookies", exc_info=True)
        return {}

    @property
    def body(self):
        from ..runtime_storage import runtime

        storage = self.storage or runtime
        body, _ = storage.get_request_input_preview()
        return body

    @property
    def remote_addr(self):
        """Remote IP address."""
        return to_unicode_safe(self.get_raw_header("REMOTE_ADDR"))

    @property
    def hostname(self):
        return to_unicode_safe(self.get_raw_header("HTTP_HOST", self.get_raw_header("SERVER_NAME")))

    @property
    def path(self):
        return quote(self.get_raw_header("SCRIPT_NAME", "")) + quote(
            self.get_raw_header("PATH_INFO", "")
        )

    @property
    def query_string(self):
        return to_unicode_safe(self.get_raw_header("QUERY_STRING"))

    @property
    def method(self):
        return to_unicode_safe(self.get_raw_header("REQUEST_METHOD"))

    @property
    def client_user_agent(self):
        return to_unicode_safe(self.get_raw_header("HTTP_USER_AGENT"))

    @property
    def referer(self):
        return to_unicode_safe(self.get_raw_header("HTTP_REFERER"))

    @property
    def scheme(self):
        return to_unicode_safe(self.get_raw_header("wsgi.url_scheme"))

    @property
    def server_port(self):
        return to_unicode_safe(self.get_raw_header("SERVER_PORT"))

    @property
    def remote_port(self):
        return to_unicode_safe(self.get_raw_header("REMOTE_PORT"))


class WSGIRequest(BaseWSGIRequest):
    """ Helper around raw wsgi environ
    """

    def __init__(self, environ, storage=None):
        super(WSGIRequest, self).__init__(storage=storage)
        self.environ = environ

    @property
    def raw_headers(self):
        return self.environ


class WSGIResponse(BaseResponse):
    """Helper around raw WSGI response."""

    def __init__(self, status, response_headers={}, body=None):
        self.status = status
        self.body = body
        if isinstance(response_headers, Mapping):
            self.headers = response_headers
        elif isinstance(response_headers, Iterable):
            self.headers = dict(response_headers)
        else:
            raise ValueError("Unknown WSGI response header type")

    @property
    def status_code(self):
        try:
            status = self.status
            if isinstance(self.status, bytes):
                status = status.decode("latin_1")
            return int(status.split(" ", 1)[0])
        except Exception:
            LOGGER.debug("cannot parse HTTP status", exc_info=True)
            return None

    @property
    def content_type(self):
        return self.headers.get("Content-Type")

    @property
    def content_length(self):
        try:
            return int(self.headers.get("Content-Length"))
        except (ValueError, TypeError):
            return None

    @property
    def headers_no_cookies(self):
        result = {}
        for header_name, value in self.headers.items():
            name = header_name.lower().replace("_", "-")
            if name == "set-cookie":
                continue
            result[name] = value
        return result
