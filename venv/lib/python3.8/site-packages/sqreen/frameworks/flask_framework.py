# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Flask specific WSGI HTTP Request / Response stuff
"""

import sys
from copy import deepcopy
from logging import getLogger
from traceback import format_stack

from ..utils import cached_property, itervalues, to_unicode_safe
from .base import BaseResponse
from .wsgi import BaseWSGIRequest

if sys.version_info[0] >= 3:
    import urllib.parse as urlparse
else:
    import urlparse


LOGGER = getLogger(__name__)


class FlaskRequest(BaseWSGIRequest):

    def __init__(self, request, storage=None):
        super(FlaskRequest, self).__init__(storage=storage)
        self.request = request

    def preload_data(self):
        """ Some Flask properties consume the stream without keeping
        a cache of the input data. We must call preload_data first,
        otherwise get_json will eventually fail.
        """
        if hasattr(self.request, "_cached_data"):
            return True
        length = self.content_length
        # Safety, do not preload data if the body is too heavy
        # XXX: this should be a parameter.
        if length is None or length > 4096:  # 4KB
            return False
        try:
            # Fill request._cached_data
            self.request.get_data()
            # Reload request.stream to use request._cached_data
            stream = self.request._get_stream_for_parsing()
            self.request.__dict__["stream"] = stream
            if self.is_flask_api:
                # Flask-API uses request._stream
                self.request._stream = stream
        except Exception:
            LOGGER.debug("couldn't get request.data from the framework",
                         exc_info=True)
            return False
        else:
            return True

    @cached_property
    def query_params(self):
        try:
            # Convert flask QueryDict to a normal dict with values as list
            # XXX: multiple values with the same key
            return dict(self.request.args.lists())
        except Exception:
            LOGGER.debug("couldn't get request.args from the framework",
                         exc_info=True)
            return super(FlaskRequest, self).query_params

    @property
    def body(self):
        """ Get the HTTP input body from the framework cache or the
        WSGI input preview.
        """
        try:
            if self.preload_data():
                return self.request.get_data()
        except Exception:
            LOGGER.debug("couldn't get request.data from the framework",
                         exc_info=True)
        return super(FlaskRequest, self).body

    def _load_form(self):
        d = self.request.__dict__
        stream = d["stream"]
        # Parsing the form data consumes request.stream
        self.request._load_form_data()
        # Reload request.stream
        d["stream"] = stream
        rd = self.__dict__
        # XXX: multiple values with the same key
        rd["form_params"] = dict(d["form"].lists())
        rd["files_field_names"] = list(d["files"].keys())
        filenames = set()
        combined_size = 0
        for fstore in itervalues(d["files"]):
            fn = fstore.filename
            if fn:
                filenames.add(fn)
            cl = fstore.content_length
            if cl is not None:
                combined_size += cl
        rd["filenames"] = list(filenames)
        rd["combined_file_size"] = combined_size

    @cached_property
    def form_params(self):
        try:
            if self.preload_data():
                self._load_form()
                return self.form_params
        except Exception:
            LOGGER.debug("couldn't get request.form from framework",
                         exc_info=True)
        return super(FlaskRequest, self).form_params

    @cached_property
    def files_field_names(self):
        try:
            if self.preload_data():
                self._load_form()
                return self.files_field_names
        except Exception:
            LOGGER.debug("couldn't get request.files from framework",
                         exc_info=True)
        return []

    @cached_property
    def filenames(self):
        try:
            if self.preload_data():
                self._load_form()
                return self.filenames
        except Exception:
            LOGGER.debug("couldn't get request.files from framework",
                         exc_info=True)
        return []

    @cached_property
    def combined_file_size(self):
        try:
            if self.preload_data():
                self._load_form()
                return self.combined_file_size
        except Exception:
            LOGGER.debug("couldn't get request.files from framework",
                         exc_info=True)
        return None

    @cached_property
    def cookies_params(self):
        try:
            return dict(self.request.cookies)
        except Exception:
            LOGGER.debug("couldn't get request.cookies from framework",
                         exc_info=True)
        return super(FlaskRequest, self).cookies_params

    @cached_property
    def _json(self):
        json_params = self.request.get_json(silent=True)
        return deepcopy(json_params)

    @property
    def json_params(self):
        try:
            if self.preload_data():
                return self._json
        except Exception:
            LOGGER.debug("couldn't get request.json from the framework",
                         exc_info=True)
        return super(FlaskRequest, self).json_params

    @property
    def remote_addr(self):
        """Remote IP address."""
        return to_unicode_safe(self.get_raw_header("REMOTE_ADDR"))

    @property
    def hostname(self):
        try:
            url = self.request.url_root
            return urlparse.urlparse(url).netloc
        except Exception:
            LOGGER.debug("couldn't get request.get_host from the framework",
                         exc_info=True)
            return None

    @property
    def method(self):
        return to_unicode_safe(self.request.method)

    @property
    def referer(self):
        return self.request.referrer

    @property
    def client_user_agent(self):
        return to_unicode_safe(self.request.user_agent.string)

    @property
    def route(self):
        """Request route."""
        url_rule = getattr(self.request, "url_rule", None)
        # If a custom rule_class is used in the app, the rule attribute might
        # be missing.
        return getattr(url_rule, "rule", None)

    @property
    def path(self):
        return self.request.path

    @property
    def scheme(self):
        return to_unicode_safe(self.request.scheme)

    @property
    def server_port(self):
        return to_unicode_safe(self.get_raw_header("SERVER_PORT"))

    @property
    def remote_port(self):
        return to_unicode_safe(self.get_raw_header("REMOTE_PORT"))

    @property
    def raw_headers(self):
        return self.request.environ

    @property
    def caller(self):
        return format_stack()

    @property
    def view_params(self):
        return self.request.view_args

    @property
    def is_flask_api(self):
        """ Detect a Flask API request. """
        return hasattr(self.request, "empty_data_class") \
            and "flask_api" in sys.modules

    @staticmethod
    def is_debug():
        try:
            from flask import current_app

            return bool(current_app.debug)
        except Exception:
            LOGGER.debug("couldn't get current_app.debug", exc_info=True)
            return False


class FlaskResponse(BaseResponse):

    def __init__(self, response):
        self.response = response

    @property
    def status_code(self):
        return self.response.status_code

    @cached_property
    def content_type(self):
        return self.response.headers.get("Content-Type")

    @cached_property
    def content_length(self):
        try:
            return int(self.response.headers.get("Content-Length"))
        except (ValueError, TypeError):
            return None

    @cached_property
    def headers_no_cookies(self):
        result = {}
        for header_name, value in self.response.items():
            name = header_name.lower().replace("_", "-")
            if name == "set-cookie":
                continue
            result[name] = value
        return result

    @cached_property
    def body(self):
        try:
            cl = self.response.content_length
            if cl is not None and cl < 4096:
                return self.response.get_data(as_text=True)
        except Exception:
            pass
        return None
