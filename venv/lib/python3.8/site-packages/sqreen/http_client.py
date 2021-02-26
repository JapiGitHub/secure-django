# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Low-level HTTP interaction with sqreen API
"""
import codecs
import json
import os
import sys
from datetime import datetime
from json import JSONEncoder

from .__about__ import __version__
from ._vendors.urllib3 import (  # type: ignore
    PoolManager,
    ProxyManager,
    Retry,
    make_headers,
)
from .exceptions import (
    InvalidJsonResponse,
    InvalidStatusCodeResponse,
    StatusFailedResponse,
)
from .utils import Iterable, Mapping, is_string, is_unicode

if sys.version_info[0] < 3:
    import urlparse
else:
    import urllib.parse as urlparse


IS_PYTHON_3 = sys.version_info.major == 3


class SqreenJSONEncoder(JSONEncoder):
    """ Custom JsonEncoder which can handle datetime objects
    >>> from datetime import datetime
    >>> date = datetime(2016, 3, 22, 14, 43, 14, 742306)
    >>> json.dumps(date, cls=SqreenJSONEncoder)
    '"2016-03-22T14:43:14.742306"'
    >>> json.dumps(2 + 1j, cls=SqreenJSONEncoder)
    '"(2+1j)"'
    >>> class Fail(object):
    ...     def __repr__(self):
    ...         raise NotImplementedError("Oups")
    ...
    >>> f = Fail()
    >>> json.dumps(f, cls=SqreenJSONEncoder)
    '"instance of type <class \\'sqreen.http_client.Fail\\'>"'
    """

    def default(self, obj):

        if isinstance(obj, datetime):
            return obj.isoformat()

        # Process bytes for python3
        if IS_PYTHON_3 and isinstance(obj, bytes):
            return obj.decode("utf-8", errors="ascii_to_hex")

        # For unknows types, JSONEncoder will raise a TypeError, instead,
        # returns obj repr
        try:
            return repr(obj)
        # If failing, return a fallback string here with the class name
        except Exception:
            return "instance of type {}".format(repr(obj.__class__))


def ascii_to_hex(exception):
    """ On unicode decode error (bytes -> unicode error), tries to replace
    invalid unknown bytes by their hex notation.
    """
    if isinstance(exception, UnicodeDecodeError):
        obj = exception.object
        start = exception.start
        end = exception.end

        invalid_part = obj[start:end]
        result = []

        for character in invalid_part:
            # Python 2 strings
            if is_string(character):
                result.append(u"\\x{}".format(character.encode("hex")))
            # Python 3 int
            elif isinstance(character, int):
                result.append(u"\\{}".format(hex(character)[1:]))
            else:
                raise exception
        result = ("".join(result), end)
        return result

    raise exception


codecs.register_error("ascii_to_hex", ascii_to_hex)


def encode_payload(payload):
    """ Tries to encode a payload into JSON, if not working, reencode the
    payload and retry to encode it into JSON.
    """
    try:
        return json.dumps(
            payload, separators=(",", ":"), cls=SqreenJSONEncoder
        )
    except UnicodeDecodeError:
        reencoded_payload = reencode_payload(payload)
        return json.dumps(
            reencoded_payload, separators=(",", ":"), cls=SqreenJSONEncoder
        )


def reencode_payload(payload):
    """ Do everything necessary to be able to encode a payload into JSON
    """
    if is_string(payload):
        return _reencode_string(payload)
    elif isinstance(payload, Mapping):
        return {
            _reencode_string(key): reencode_payload(value)
            for key, value in payload.items()
        }
    elif isinstance(payload, Iterable):
        return [reencode_payload(item) for item in payload]
    else:
        return payload


def _reencode_string(string):
    """ Ensure that the string is encodable into JSON
    """
    if not is_unicode(string):
        return string.decode("utf-8", errors="ascii_to_hex")

    return string


def where_crt():
    """ Returns the path of the bundled crt
    """
    current_file = os.path.split(__file__)[0]
    return os.path.join(current_file, "ca.crt")


USER_AGENT = "sqreen-python/{}".format(__version__)


class Urllib3Connection(object):
    """ Class responsible for making http request to sqreen API,

    handle connection pooling, retry and inbound/outbound formatting
    """

    RETRY_STATUS = {500, 502, 503, 504, 408}
    # Beware that the retry policy will block the Sqreen thread until
    # the request is successful.
    RETRY = Retry(
        total=5,
        method_whitelist=False,
        status_forcelist=RETRY_STATUS,
        backoff_factor=1,
    )
    RETRY_LONG = Retry(
        total=15,
        method_whitelist=False,
        status_forcelist=RETRY_STATUS,
        backoff_factor=1,
    )
    RETRY_ONCE = Retry(
        total=1,
        method_whitelist=False,
        status_forcelist=RETRY_STATUS,
        backoff_factor=1,
    )

    PATH_PREFIX = "/sqreen/"

    def __init__(self, server_url, proxy_url=None, user_agent=USER_AGENT,
                 use_legacy_url=False):
        self.server_url = server_url
        self.proxy_url = proxy_url
        self.parsed_server_url = urlparse.urlparse(server_url)
        self.user_agent = user_agent
        self.use_legacy_url = use_legacy_url

        # Disable certificate pinning when using the newer domain
        ca_certs = where_crt() if use_legacy_url else None
        if self.proxy_url:
            self.connection = ProxyManager(
                proxy_url,
                cert_reqs="CERT_REQUIRED",
                ca_certs=ca_certs,
                timeout=60,
            )
        else:
            self.connection = PoolManager(
                cert_reqs="CERT_REQUIRED", ca_certs=ca_certs, timeout=60
            )

    def get_user_agent(self):
        return getattr(self, "_user_agent", USER_AGENT)

    def set_user_agent(self, value):
        self.base_headers = make_headers(
            keep_alive=True, accept_encoding=True, user_agent=value
        )
        self._user_agent = value

    user_agent = property(get_user_agent, set_user_agent)

    def _url(self, url):
        """ Format and return an url based on instance path prefix
        """
        path = urlparse.urljoin(self.PATH_PREFIX, url)
        return urlparse.urlunparse(
            (
                self.parsed_server_url[0],
                self.parsed_server_url[1],
                path,
                None,
                None,
                None,
            )
        )

    def post(self, endpoint, data=None, headers=None, retries=None):
        """ Post a request to the backend
        """
        url = self._url(endpoint)

        if headers is None:
            headers = {}

        if data is not None:
            data = encode_payload(data)
            headers["Content-Type"] = "application/json"

        # Add base headers
        headers.update(self.base_headers)

        response = self.connection.urlopen(
            "POST", url, headers=headers, body=data, retries=retries
        )

        return self._parse_response(response)

    def get(self, endpoint, headers=None, retries=None):
        """ Get an endpoint in the backend
        """
        url = self._url(endpoint)

        if headers is None:
            headers = {}

        # Add base headers
        headers.update(self.base_headers)

        response = self.connection.urlopen(
            "GET", url, headers=headers, retries=retries
        )

        return self._parse_response(response)

    def _parse_response(self, response):
        """ Try to decode response body to json
        """
        if response.status < 200 or response.status >= 300:
            raise InvalidStatusCodeResponse(response.status, response.data)

        try:
            json_response = json.loads(response.data.decode("utf-8"))
        except ValueError as exc:
            raise InvalidJsonResponse(exc)

        if json_response.get("status", False) is False:
            raise StatusFailedResponse(json_response)

        return json_response
