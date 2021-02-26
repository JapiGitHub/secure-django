# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Helper classes for runtime storage."""

import threading
from collections import defaultdict

import pkg_resources

from .exceptions import RequestStoreFull
from .frameworks.blank import BlankRequest, BlankResponse
from .payload_creator import PayloadCreator
from .request_recorder import RequestRecorder
from .utils import HAS_ASYNCIO

REQUEST_STORE_MAX_ITEMS = 1000


class RuntimeStorage(object):
    """Runtime storage objects."""

    default_request_class = BlankRequest
    default_response_class = BlankResponse

    def __init__(self, store=None):
        if store is None:
            store = _ThreadLocalStore()
        self.store = store
        # Let's not set store attributes here: the event loop may not be
        # started yet.
        self.payload_creator = PayloadCreator()
        self.attack_http_code = 403

    def store_request(self, request, **kwargs):
        """Store a request."""
        self.store.set("current_request", request)
        request_recorder = self.store.get("request_recorder")
        if request_recorder is None:
            # First request.
            request_recorder = RequestRecorder()
            self.store.set("request_recorder", request_recorder)
        request_recorder.start_request(request, **kwargs)

    def store_request_default(self, request, **kwargs):
        """Store a request, unless a request is already stored."""
        current_request = self.get_current_request()
        if current_request is None:
            self.store_request(request, **kwargs)

    def get_current_request(self):
        """Return the request currently processed.

        Return None if no request is stored.
        """
        return self.store.get("current_request")

    def clear_request(self, queue=None, observation_queue=None):
        """Clear the stored request."""
        self.store.delete("whitelist_match")
        self.store.delete("current_request_input_preview")
        self.store.delete("current_request_store")
        current_request = self.store.delete("current_request")
        current_response = self.store.delete("current_response")
        request_recorder = self.store.get("request_recorder")
        if request_recorder is not None:
            request_recorder.end_request()
            if current_request is not None and queue is not None \
                    and observation_queue is not None:
                request_recorder.flush(
                    current_request, current_response,
                    self.payload_creator, queue, observation_queue
                )
            else:
                request_recorder.clear()

    def store_request_input_preview(self, preview, end_of_input):
        """Store the request input stream body preview."""
        self.store.set("current_request_input_preview",
                       (preview, end_of_input))

    def get_request_input_preview(self):
        """Get the request input stream body preview."""
        return self.store.get("current_request_input_preview", (None, None))

    def update_request_store(self, **data):
        """Update the request store with new data."""
        store = self.store.setdefault("current_request_store", defaultdict(lambda: None))
        if len(store) + len(data) > REQUEST_STORE_MAX_ITEMS:
            raise RequestStoreFull("request store capacity exceeded")
        store.update(data)

    def get_request_store(self):
        """Get the request store."""
        return self.store.get("current_request_store", defaultdict(lambda: None))

    def store_response(self, response):
        """Store a response."""
        self.store.set("current_response", response)

    def store_response_default(self, response):
        """Store a response, unless a response is already stored."""
        current_response = self.get_current_response()
        if current_response is None:
            self.store_response(response)

    def get_current_response(self):
        """Returns the current response or None."""
        return self.store.get("current_response")

    def clear_response(self):
        """Clear the stored response."""
        self.store.delete("current_response")

    @property
    def request_sq_time(self):
        """Proxy to RequestRecorder request_sq_time property."""
        request_recorder = self.store.get("request_recorder")
        if request_recorder is None:
            request_recorder = RequestRecorder()
            self.store.set("request_recorder", request_recorder)
        return request_recorder.request_sq_time

    def record_overtime(self, name, at=None):
        """Mark the current request as overtime."""
        request_recorder = self.store.get("request_recorder")
        if request_recorder is None:
            request_recorder = RequestRecorder()
            self.store.set("request_recorder", request_recorder)
        request_recorder.record_overtime(name, at=at)

    def trace(self, *args, **kwargs):
        """Proxy to RequestRecorder trace method."""
        request_recorder = self.store.get("request_recorder")
        if request_recorder is None:
            request_recorder = RequestRecorder()
            self.store.set("request_recorder", request_recorder)
        return request_recorder.trace(*args, **kwargs)

    def observe(self, *args, **kwargs):
        """Proxy to RequestRecorder observe method."""
        request_recorder = self.store.get("request_recorder")
        if request_recorder is None:
            request_recorder = RequestRecorder()
            self.store.set("request_recorder", request_recorder)
        request_recorder.observe(*args, **kwargs)

    def get_whitelist_match(self):
        """Return the whitelisted path or IP matching the current request.

        Return False if the request is not whitelisted.
        """
        return self.store.get("whitelist_match", None)

    def set_whitelist_match(self, match):
        """Store a whitelisted path or IP matching the current request.
        """
        self.store.set("whitelist_match", match)

    def store_current_args(self, fake_args):
        """For daemon only: store the faked list of arguments."""
        self.store.set("arguments", fake_args)

    def get_current_args(self, args=None):
        """For daemon only: get the faked list of arguments."""
        return self.store.get("arguments", args)

    def store_cmd_arguments(self, cmd_args):
        """Alternative of store_current_args that doesn't destroy data"""
        self.store.set("cmd_args", cmd_args)

    def get_cmd_arguments(self):
        """dict ba expr -> its resolution by the extension"""
        return self.store.get("cmd_args")

    def store_extension_data(self, key, value):
        """Store extension data associated to a key."""
        extension_data = self.store.get("extension_data")
        if extension_data is None:
            extension_data = {}
            self.store.set("extension_data", extension_data)
        extension_data[key] = value

    def get_extension_data(self, key):
        """Returns the extension data associated to key or None."""
        return self.store.get("extension_data", {}).get(key)

    def clear_extension_data(self):
        """Clear the extension data."""
        self.store.delete("extension_data")


class _ThreadLocalStore(object):
    """Wrap a threading.local object into a store interface."""

    def __init__(self):
        self.local = threading.local()

    def get(self, key, default=None):
        """Return the value associated to the key.

        Fallback to default if the key is missing.
        """
        return getattr(self.local, key, default)

    def set(self, key, value):
        """Map a key to a value."""
        setattr(self.local, key, value)

    def setdefault(self, key, value):
        """If a key is not set, map it to a value."""
        return self.local.__dict__.setdefault(key, value)

    def delete(self, key):
        """Delete a key."""
        return self.local.__dict__.pop(key, None)


_THREADED_FRAMEWORKS = ("Django", "Flask", "pyramid")

_ASYNC_FRAMEWORKS = ("aiohttp",)


def _get_store():
    """Return a store object suited for the current framework."""
    if HAS_ASYNCIO:
        pkg_names = set(
            pkg_info.project_name for pkg_info in pkg_resources.working_set
        )
        for framework in _THREADED_FRAMEWORKS:
            if framework in pkg_names:
                return _ThreadLocalStore()
        for framework in _ASYNC_FRAMEWORKS:
            if framework in pkg_names:
                from . import async_context

                return async_context
    return _ThreadLocalStore()


def get_runtime_storage():
    """Return a runtime storage instance suited for the current framework."""
    return RuntimeStorage(_get_store())


runtime = get_runtime_storage()
