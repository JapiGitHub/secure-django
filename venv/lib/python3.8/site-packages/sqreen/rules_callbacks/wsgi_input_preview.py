# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Record request context
"""
import sys
from io import BytesIO
from logging import getLogger

from ..rules import RuleCallback

LOGGER = getLogger(__name__)


class WSGIInputWrapper:
    """
    Wrap wsgi.input and keep a preview of the read bytes.
    """

    DEFAULT_MAX_PREVIEW_LENGTH = 4096

    def __init__(self, rule, original, length_hint=None,
                 max_preview_length=None):
        self.rule = rule
        self.original = original
        self.original_read = 0
        self.original_length_hint = length_hint \
            if length_hint is not None else sys.maxsize
        self.preview_max_length = max_preview_length \
            if max_preview_length is not None \
            else self.DEFAULT_MAX_PREVIEW_LENGTH
        self.preview_remaining = self.preview_max_length
        self.buf = BytesIO()

    def preview_callback(self, preview, end_of_input):
        """
        Callback to get the WSGI input preview when ready.
        """
        LOGGER.debug("Got a preview of %d bytes (end of input %r)",
                     len(preview), end_of_input)
        self.rule.storage.store_request_input_preview(preview, end_of_input)

    def _feed_preview(self, data, size_hint=0):
        if not self.preview_remaining:
            return
        try:
            self.original_read += len(data)
            preview = data[:self.preview_remaining]
            self.buf.write(preview)
            self.preview_remaining -= len(preview)
            # End of stream or preview is ready
            end_of_input = not data or size_hint is None \
                or size_hint < 0 or len(data) < size_hint \
                or self.original_read >= self.original_length_hint
            if not self.preview_remaining or end_of_input:
                try:
                    self.preview_callback(self.buf.getvalue(), end_of_input)
                finally:
                    self.preview_remaining = 0
                    # Don't keep the reference will free the buf memory
                    self.buf = None
        except Exception as e:
            self.rule.record_exception(e, sys.exc_info())

    def read(self, *args, **kwargs):
        data = self.original.read(*args, **kwargs)
        size = args[0] if args else kwargs.get("size")
        self._feed_preview(data, size_hint=size)
        return data

    def readline(self, *args, **kwargs):
        data = self.original.readline(*args, **kwargs)
        self._feed_preview(data)
        return data

    def readlines(self, *args, **kwargs):
        it = self.original.readlines(*args, **kwargs)
        for data in it:
            self._feed_preview(data)
            yield data
        else:
            self._feed_preview(b"")

    def __iter__(self):
        for data in self.original:
            self._feed_preview(data)
            yield data
        else:
            self._feed_preview(b"")


class WSGIInputPreview(RuleCallback):
    """ Get a preview of the WSGI input stream.
    """

    INTERRUPTIBLE = False

    def pre(self, instance, args, kwargs, options):
        """ Replace the WSGI input stream with our wrapper to get a
        preview of the body.
        """
        # Do not copy the environ but mutate it because some
        # webservers keep a reference on the original environ
        # and do not except the reference to change.
        environ = args[0]
        input = environ.get("wsgi.input")
        current_request = self.storage.get_current_request()
        if input is not None and current_request is not None \
                and not isinstance(input, WSGIInputWrapper):
            max_preview_length = self.data.get("max_preview_length")
            input_wrapper = WSGIInputWrapper(
                self, input, current_request.content_length,
                max_preview_length)
            environ["wsgi.input"] = input_wrapper
        # Return a modify_args because we should replace
        # the environ, but the mutatation is enough
        return {
            "status": "modify_args",
            "args": ([environ], kwargs)
        }
