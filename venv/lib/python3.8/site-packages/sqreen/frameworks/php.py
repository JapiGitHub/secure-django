# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Generic WSGI HTTP Request / Response stuff
"""
import sys
from collections import defaultdict
from itertools import chain
from logging import getLogger

from ..exceptions import MissingDataException
from ..utils import to_unicode_safe
from .base import BaseRequest, BaseResponse
from .ip_utils import get_real_user_ip

if sys.version_info[0] < 3:
    import urlparse
else:
    import urllib.parse as urlparse


LOGGER = getLogger(__name__)


class PHPRequest(BaseRequest):
    """ Helper around PHP request
    """

    def __init__(self, environ=None, storage=None):
        super(PHPRequest, self).__init__(storage=storage)
        if environ is None:
            environ = {}
        self.environ = environ.get("request", {})

    @property
    def body(self):
        """Return the body of the request if present"""
        return self.environ.get("BODY")

    @property
    def query_params(self):
        """ Return parsed query string from request
        """
        return self.environ.get("PARSED_REQ_PARAMS", {}).get('"GET"', {})

    @property
    def form_params(self):
        return self.environ.get("PARSED_REQ_PARAMS", {}).get('"POST"', {})

    @property
    def cookies_params(self):
        return self.environ.get("PARSED_REQ_PARAMS", {}).get('"COOKIE"', {})

    @property
    def query_params_values(self):
        """ Return only query values as a list
        """
        return list(chain.from_iterable(self.query_params.values()))

    @property
    def remote_addr(self):
        """Remote IP address."""
        return self.environ.get("REMOTE_ADDR")

    @property
    def raw_client_ip(self):
        return get_real_user_ip(
            self.environ.get("REMOTE_ADDR"), *self.iter_client_ips()
        )

    @property
    def hostname(self):
        return to_unicode_safe(self.get_raw_header("HTTP_HOST", self.environ.get("SERVER_NAME")))

    @property
    def method(self):
        return self.environ.get("REQUEST_METHOD", "")

    @property
    def client_user_agent(self):
        return to_unicode_safe(self.get_raw_header("HTTP_USER_AGENT", ""))

    @property
    def referer(self):
        return to_unicode_safe(self.get_raw_header("HTTP_REFERER", None))

    @property
    def scheme(self):
        return self.environ.get("URL_SCHEME")

    @property
    def server_port(self):
        return self.environ.get("SERVER_PORT")

    @property
    def remote_port(self):
        return self.environ.get("REMOTE_PORT")

    @property
    def path(self):
        request_uri = self.environ.get("REQUEST_URI", "")
        try:
            # REQUEST_URI can sometimes contain a full URL
            # in this case we parse it and try to extract the path.
            return urlparse.urlparse(request_uri).path
        except ValueError:
            # If the parsing has failed, warn about it and
            # return the initial value. In fact, some path
            # can be misinterpreted as invalid URL by python's
            # urlparse (for example //test] is an invalid IPv6
            # URL but a somewhat valid path).
            LOGGER.debug("request with invalid URI path: %s",
                         request_uri, exc_info=True)
        return request_uri

    @property
    def request_uri(self):
        request_uri = self.environ.get("REQUEST_URI", "")
        try:
            # REQUEST_URI can sometimes contain a full URL
            # in this case we parse it and try to extract the path.
            _, _, path, query_string, _ = urlparse.urlsplit(request_uri)
            return urlparse.urlunsplit(("", "", path, query_string, ""))
        except ValueError:
            # If the parsing has failed, warn about it and
            # return the initial value. In fact, some path
            # can be misinterpreted as invalid URL by python's
            # urlparse (for example //test] is an invalid IPv6
            # URL but a somewhat valid path).
            LOGGER.debug("request with invalid URI path: %s",
                         request_uri, exc_info=True)
        return request_uri

    @property
    def raw_headers(self):
        return self.environ.get("HEADERS", {})

    @property
    def request_headers(self):
        return defaultdict(lambda: None, **self.raw_headers)

    @property
    def view_params(self):
        return {}

    @property
    def json_params(self):
        return {}

    @property
    def caller(self):
        return [
            "#{count} {file_}({line}) {class_}{type_}{function}".format(
                count=i,
                file_=line.get("file", ""),
                line=line.get("line", "0"),
                class_=line.get("class", ""),
                type_=line.get("type", ""),
                function=line.get("function", ""),
            )
            for i, line in enumerate(self.raw_caller)
        ]

    @property
    def raw_caller(self):
        """The caller is only known from the PHP extension but not sent by default
        to the daemon. We then keep track of the data we are missing and notify the
        daemon by raising a MissingDataException.

        The extension data is not kept inside the request because if the rule is executed
        outside a request context, the request instance is a placeholder and won't
        survive the callback execution."""
        from ..runtime_storage import runtime

        storage = self.storage or runtime
        value = storage.get_extension_data("#.caller")
        if value is None:
            raise MissingDataException("#.caller")
        return value


class PHPResponse(BaseResponse):
    """Helper around PHP response."""

    def __init__(self, status, response_headers={}):
        self.status = int(status)
        self.headers = response_headers

    @property
    def status_code(self):
        return self.status

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
