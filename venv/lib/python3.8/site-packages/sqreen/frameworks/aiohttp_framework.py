# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Wrapper class for aiohttp request objects."""
import json
from logging import getLogger

from ..utils import cached_property, to_unicode_safe
from .base import BaseRequest, BaseResponse

LOGGER = getLogger(__name__)


def multidict_to_dict(multidict):
    """Convert a multidict instance to a regular dict.

    Each key in the resulting dict is associated to the list of values mapped
    to this key in the original multidict.
    """
    getter = getattr(multidict, "getall", multidict.get)
    return {key: getter(key) for key in multidict}


def get_request_remote(request):
    """Get the remote IP address of an aiohttp.web.Request object.

    Return a string with the remote IP address if it could be determined, None
    otherwise.

    This function calls the property request.remote if it is defined
    (introduced in aiohttp 2.3). If not, it mimics aiohttp implementation and
    fallbacks on socket.getpeername.
    """
    if hasattr(request, "remote"):
        return request.remote
    peername = request.transport.get_extra_info("peername")
    if isinstance(peername, (list, tuple)):
        return peername[0]
    else:
        return peername


class AioHTTPRequest(BaseRequest):
    """Wrapper class for aiohttp request objects."""

    def __init__(self, request):
        super(AioHTTPRequest, self).__init__()
        self.request = request

    @property
    def server_port(self):
        """Server port number."""
        sockname = self.request.transport.get_extra_info("sockname")
        return sockname[1]

    @property
    def remote_port(self):
        """Client port number."""
        peername = self.request.transport.get_extra_info("peername")
        return peername[1]

    @property
    def method(self):
        """Request method."""
        return self.request.method

    @property
    def scheme(self):
        """Request scheme (http or https)."""
        return self.request.scheme

    @property
    def hostname(self):
        """Request host."""
        return self.request.host

    @property
    def route(self):
        """Request route."""
        match_info = getattr(self.request, "match_info", None)
        if match_info is None:
            return None
        match_info = match_info.get_info()
        if "path" in match_info:
            # Static route (PlainResource).
            return match_info["path"]
        elif "formatter" in match_info:
            # Pattern-based route (DynamicResource).
            return match_info["formatter"]
        else:
            # HTTP exceptions, e.g. 404.
            return None

    @property
    def path(self):
        """Request path."""
        return self.request.path

    def query_string(self):
        """Request query string."""
        return self.request.query_string

    @property
    def request_uri(self):
        """Request URI."""
        return self.request.rel_url.path_qs

    @cached_property
    def raw_headers(self):
        """Dictionary of request headers.

        Headers are encoded in WSGI format, described in PEP 3333.
        """
        headers = {
            "REQUEST_METHOD": self.request.method,
            "SCRIPT_NAME": "",  # Mandatory as per PEP 3333.
            "PATH_INFO": self.request.path,
            "QUERY_STRING": self.request.query_string,
            "SERVER_NAME": self.hostname,
            "SERVER_PORT": str(self.server_port),
            "SERVER_PROTOCOL": "HTTP/{}.{}".format(*self.request.version),
            "wsgi.scheme": self.request.scheme,
        }
        remote = get_request_remote(self.request)
        if remote is not None:
            headers["REMOTE_ADDR"] = remote
        if self.request.content_length is not None:
            headers["CONTENT_LENGTH"] = str(self.request.content_length)
        if self.request.content_type is not None:
            headers["CONTENT_TYPE"] = self.request.content_type
        for key, value in self.request.headers.items():
            name = "HTTP_{}".format(key.replace("-", "_").upper())
            headers[name] = value
        return headers

    @property
    def referer(self):
        """Request referer."""
        return to_unicode_safe(self.get_raw_header("HTTP_REFERER"))

    @property
    def client_user_agent(self):
        """User agent."""
        return to_unicode_safe(self.get_raw_header("HTTP_USER_AGENT"))

    @property
    def remote_addr(self):
        """Remote IP address."""
        return to_unicode_safe(self.get_raw_header("REMOTE_ADDR"))

    @cached_property
    def query_params(self):
        """Dictionary of query parameters."""
        return multidict_to_dict(self.request.query)

    @cached_property
    def _form(self):
        post_params = self.request._post
        return multidict_to_dict(post_params)

    @property
    def form_params(self):
        """Dictionary of form parameters."""
        # Only return the form parameters when the app already read them.
        post_params = self.request._post
        if post_params is not None:
            return self._form
        return {}

    @cached_property
    def cookies_params(self):
        """Dictionary of cookies parameters."""
        return multidict_to_dict(self.request.cookies)

    @cached_property
    def _json(self):
        data = self.request._read_bytes.decode(
            self.request.charset or "utf-8")
        return json.loads(data)

    @property
    def json_params(self):
        """Request body, decoded as JSON."""
        try:
            # Only return the JSON parameters when the body was already read
            # by the app.
            if self.request._read_bytes is not None:
                return self._json
        except Exception:
            LOGGER.debug("couldn't get request.json from the framework",
                         exc_info=True)
        return {}

    @property
    def view_params(self):
        """Dictionary of view arguments that matched the request."""
        return self.request.match_info


class AioHTTPResponse(BaseResponse):

    def __init__(self, response):
        self.response = response

    @property
    def status_code(self):
        return self.response.status

    @property
    def content_type(self):
        return self.response.headers.get("Content-Type")

    @property
    def content_length(self):
        try:
            return int(self.response.content_length)
        except (ValueError, TypeError):
            return None

    @property
    def headers_no_cookies(self):
        result = {}
        for header_name, value in self.response.headers.items():
            name = header_name.lower().replace("_", "-")
            if name == "set-cookie":
                continue
            result[name] = value
        return result
