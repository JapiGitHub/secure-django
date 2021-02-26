# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Base Request class
"""
import json
import logging
import sys
import traceback
import uuid
from collections import defaultdict

from ..config import CONFIG
from ..remote_exception import traceback_formatter
from ..utils import HAS_TYPING, cached_property, flatten, to_unicode_safe
from .ip_utils import get_real_user_ip

if sys.version_info[0] >= 3:
    from urllib.parse import unquote_to_bytes, urlencode
else:
    from urllib import unquote as unquote_to_bytes, urlencode

if HAS_TYPING:
    from typing import List


LOGGER = logging.getLogger(__name__)


# Header name that we need to sends back on attack in order to compute the
# real user ip
DEFAULT_CLIENT_IP_HEADERS = (
    "HTTP_X_FORWARDED_FOR",
    "X_FORWARDED_FOR",
    "HTTP_X_REAL_IP",
    "HTTP_CLIENT_IP",
    "HTTP_X_FORWARDED",
    "HTTP_X_CLUSTER_CLIENT_IP",
    "HTTP_FORWARDED_FOR",
    "HTTP_FORWARDED",
    "HTTP_VIA",
    "REMOTE_ADDR",
)
CLIENT_IP_HEADERS = []  # type: List[str]


def load_config_ip_header():
    del CLIENT_IP_HEADERS[:]
    if CONFIG["IP_HEADER"]:
        CLIENT_IP_HEADERS.append(
            "HTTP_{}".format(CONFIG["IP_HEADER"].upper().replace("-", "_")))
    CLIENT_IP_HEADERS.extend(DEFAULT_CLIENT_IP_HEADERS)


load_config_ip_header()


class BaseRequest(object):
    """ Base request class common to all request wrapper classes.
    """

    def __init__(self, storage=None):
        self.storage = storage

    @property
    def remote_addr(self):
        raise NotImplementedError

    @property
    def hostname(self):
        raise NotImplementedError

    @property
    def method(self):
        raise NotImplementedError

    @property
    def referer(self):
        raise NotImplementedError

    @property
    def client_user_agent(self):
        raise NotImplementedError

    @property
    def path(self):
        raise NotImplementedError

    @property
    def scheme(self):
        raise NotImplementedError

    @property
    def server_port(self):
        raise NotImplementedError

    @property
    def remote_port(self):
        raise NotImplementedError

    @property
    def raw_headers(self):
        raise NotImplementedError

    @property
    def form_params(self):
        raise NotImplementedError

    @property
    def query_params(self):
        raise NotImplementedError

    @property
    def view_params(self):
        raise NotImplementedError

    @property
    def query_string(self):
        data = []
        for key, values in self.query_params.items():
            if isinstance(values, list):
                for value in values:
                    data.append((key, value))
            else:
                data.append((key, values))
        return urlencode(data)

    @property
    def request_uri(self):
        uri = [self.path]
        query_string = self.query_string
        if query_string:
            uri.append("?")
            query_string = query_string.replace('+', ' ')
            # convert the query string to bytes
            if sys.version_info[0] >= 3 and hasattr(query_string, "encode"):
                query_string = query_string.encode(errors="surrogatepass")
            # unescape non-ASCII chars and try to convert the final result
            # to unicode
            uri.append(to_unicode_safe(unquote_to_bytes(query_string)))
        return "".join(uri)

    @cached_property
    def json_params(self):
        try:
            ct = to_unicode_safe(self.content_type)
            data = self.body
            if ct is not None and ct.startswith("application/json") and data:
                try:
                    return json.loads(data)
                except TypeError:
                    # Python 3.5 does not detect argument encoding, enforce UTF-8
                    return json.loads(to_unicode_safe(data))
        except Exception:
            LOGGER.debug("couldn't parse input json", exc_info=True)
        return {}

    @property
    def cookies_params(self):
        raise NotImplementedError

    @property
    def body(self):
        raise NotImplementedError

    @property
    def body_params(self):
        return self.form_params or self.json_params

    @cached_property
    def request_uuid(self):
        return uuid.uuid4()

    @property
    def request_id(self):
        return self.request_uuid.hex

    MAX_UUID = float((1 << 128) - 1)

    @property
    def request_rate(self):
        return self.request_uuid.int / self.MAX_UUID

    @property
    def request_payload(self):
        """ Returns current request payload with the backend expected field
        name. All fields should be serializable to JSON.
        """
        if CONFIG["STRIP_HTTP_REFERER"]:
            referer = None
        else:
            referer = self.referer

        return {
            "rid": self.request_id,
            "remote_ip": self.remote_addr,
            "client_ip": self.client_ip,
            "host": self.hostname,
            "verb": self.method,
            "referer": referer,
            "user_agent": self.client_user_agent,
            "path": self.path,
            "scheme": self.scheme,
            "port": self.server_port,
            "remote_port": self.remote_port,
            "endpoint": self.route,
        }

    @property
    def request_params(self):
        """ Returns all the inputs that are controllable by the user.
        All fields should be serializable to JSON.
        """
        return {
            "form": self.form_params,
            "query": self.query_params,
            "other": self.view_params,
            "json": self.json_params,
            "cookies": self.cookies_params,
        }

    @property
    def request_params_list(self):
        """ Returns all the inputs that are controllable by the user without
        keys. All fields should be serializable to JSON.
        """
        return [
            self.form_params,
            self.query_params,
            self.view_params,
            self.json_params,
            self.cookies_params,
        ]

    @property
    def request_params_filtered(self):
        """ Returns all the inputs that are controllable by the user without cookies.
        This is based on the Ruby reference implementation.
        """
        ret = self.request_params
        ret.pop("cookies", None)
        return ret

    @cached_property
    def flat_request_params(self):
        """ Flatten the request params to compute the values and keys for
        quick access
        """
        _, values = flatten(self.request_params_list)
        return values

    def params_contains(self, param):
        """ Return True if the parameter given in input is present in the
        request inputs.
        """
        return param in self.flat_request_params

    @cached_property
    def request_headers(self):
        request_headers = defaultdict(lambda: None)
        for key, value in self.raw_headers.items():
            key = to_unicode_safe(key)
            if not key.startswith("HTTP_"):
                if key == "CONTENT_LENGTH" and value:
                    # Some WSGI implementations set CONTENT_LENGTH to
                    # an empty string when not set in the HTTP request.
                    # We actually prefer to consider the header not set.
                    pass
                elif key != "CONTENT_TYPE":
                    continue
            request_headers[key] = to_unicode_safe(value)
        return request_headers

    @property
    def content_type(self):
        return self.get_raw_header("CONTENT_TYPE")

    @property
    def content_length(self):
        value = self.get_raw_header("CONTENT_LENGTH")
        if value is not None:
            try:
                return int(value)
            except ValueError:
                pass
        return None

    @property
    def caller(self):
        return traceback.format_stack()

    @property
    def raw_caller(self):
        return traceback_formatter(traceback.extract_stack())

    @property
    def client_ip(self):
        """String formatted client IP address."""
        ip = self.raw_client_ip
        if ip is not None:
            return to_unicode_safe(ip)

    @cached_property
    def raw_client_ip(self):
        """Client IP address."""
        return get_real_user_ip(self.remote_addr, *self.iter_client_ips())

    def get_raw_header(self, name, default=None):
        """ Get a specific raw header."""
        return self.raw_headers.get(name, default)

    def iter_client_ips(self):
        """Yield the client IPs set in raw headers."""
        for header_name in CLIENT_IP_HEADERS:
            value = self.get_raw_header(header_name)
            if value:
                yield value

    def get_client_ips_headers(self):
        """ Return raw headers that can be used to find the real client ip
        """
        headers = []
        for header_name in CLIENT_IP_HEADERS:
            value = self.get_raw_header(header_name)
            if value:
                headers.append([header_name, to_unicode_safe(value)])

        return headers

    @property
    def headers_no_cookies(self):
        result = {}
        for header_name, value in self.request_headers.items():
            name = header_name.lower().replace("_", "-")
            if name.startswith("http-"):
                name = name[5:]
            if name == "cookie":
                continue
            result[name] = value
        return result

    @property
    def route(self):
        return None


class BaseResponse(object):

    @property
    def status_code(self):
        raise NotImplementedError

    @property
    def content_type(self):
        raise NotImplementedError

    def content_length(self):
        raise NotImplementedError

    @property
    def response_payload(self):
        """Returns the response information understood by the backend.
        """
        return {
            "status": self.status_code,
            "content_type": self.content_type,
            "content_length": self.content_length,
        }

    @property
    def headers_no_cookies(self):
        raise NotImplementedError
